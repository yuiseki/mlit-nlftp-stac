#!/usr/bin/env python3
"""catalog/ -> catalog/items.parquet, the whole catalog as one table.

Offline. Reads the JSON that `03_build_stac.py` wrote, so the two can never
disagree about anything except by being run at different times.

    duckdb -c "
      install spatial; load spatial;
      select collection_title, count(*), sum(file_size)/1e9 as gb
        from 'https://stac.yuiseki.net/mlit-nlftp/items.parquet'
       where redistribution = 'allowed' and year >= 2023
       group by 1 order by 3 desc;
    "
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mlit_nlftp_stac.geoparquet import rows_from  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", default=str(ROOT / "catalog"))
    ap.add_argument("--base-url", default="https://stac.yuiseki.net/mlit-nlftp")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    import geopandas as gpd  # noqa: PLC0415
    import pandas as pd  # noqa: PLC0415
    from shapely.geometry import shape  # noqa: PLC0415

    cat = Path(args.catalog)
    out = Path(args.out) if args.out else cat / "items.parquet"
    if not (cat / "catalog.json").exists():
        print(f"no catalog at {cat}. Run `make build` first.", file=sys.stderr)
        return 1

    titles = {}
    for p in cat.glob("collections/*/collection.json"):
        d = json.loads(p.read_text())
        titles[d["id"]] = d.get("title", "")

    items, geoms = [], []
    for p in sorted(cat.glob("collections/*/items/*.json")):
        d = json.loads(p.read_text())
        items.append(d)
        g = d.get("geometry")
        geoms.append(shape(g) if g else None)
    print(f"{len(items)} items, {sum(1 for g in geoms if g is not None)} with a geometry")

    gdf = gpd.GeoDataFrame(
        rows_from(items, titles, args.base_url.rstrip("/")),
        geometry=gpd.GeoSeries(geoms, crs="EPSG:4326"),
    )

    # Rows near each other in space near each other in the file, so a reader
    # asking about one prefecture can skip most row groups. Items with no
    # footprint have no place in that order and go last.
    located = gdf[gdf.geometry.notna()].copy()
    located["_h"] = located.geometry.hilbert_distance()
    located = located.sort_values("_h").drop(columns="_h")
    gdf = pd.concat([located, gdf[gdf.geometry.isna()]]).reset_index(drop=True)

    gdf.to_parquet(
        out,
        compression="zstd",
        write_covering_bbox=True,
        schema_version="1.1.0",
        row_group_size=5000,
    )
    size = out.stat().st_size
    print(f"{len(gdf)} rows, {size / 1024**2:.1f} MB -> {out}")

    # Read it back and ask it the question this exists to answer.
    back = gpd.read_parquet(out)
    allowed = back[back["redistribution"] == "allowed"]
    print(f"  redistribution=allowed: {len(allowed)} rows, "
          f"{allowed['file_size'].sum() / 1024**3:.1f} GB measured")
    assert len(back) == len(items), "row count changed on the way to Parquet"
    return 0


if __name__ == "__main__":
    sys.exit(main())
