from mlit_nlftp_stac import docs
from mlit_nlftp_stac.stac import doc_links

COLL = {
    "id": "A40",
    "ksj:identifier": "A40",
    "title": "津波浸水想定データ (A40)",
    "description": "都道府県から提供された津波浸水想定データ。",
    "license": "other",
    "ksj:years": [2016, 2024],
    "ksj:latest_year": 2024,
    "ksj:coordinate_system": "JGD2011 / （B, L）",
    "ksj:terms": "オープンデータ（CC_BY_4.0（一部制限））",
    "ksj:variants": [
        {
            "shapefile": None,
            "label": "属性情報",
            "columns": [
                {"name": "都道府県名", "column": "A40_001"},
                {"name": "都道府県コード", "column": "A40_002",
                 "ksj:codelist_href": "../../codelists/PrefCd.json"},
            ],
        }
    ],
    "links": [
        {"rel": "related", "href": "../P20/collection.json",
         "ksj:editorial": True, "ksj:reason": "津波浸水想定域の内と外で避難施設を数える",
         "ksj:crs_mismatch": ["JGD2011", "JGD2000"]},
        {"rel": "related", "href": "../mesh500/collection.json", "title": "同じ系列"},
    ],
}

ITEMS = [
    {"properties": {"ksj:redistribution": "allowed", "ksj:file_format": "GML"},
     "assets": {"source": {"file:size": 1_000_000_000}}},
    {"properties": {"ksj:redistribution": "check", "ksj:file_format": "GML"},
     "assets": {"source": {"file:size": 500_000_000}}},
]


def test_doc_links_are_the_pair_portolan_requires():
    links = doc_links()
    assert [l["rel"] for l in links] == ["describedby", "agents"]
    assert all(l["type"] == "text/markdown" for l in links)
    assert [l["href"] for l in links] == ["./README.md", "./AGENTS.md"]


def test_collection_readme_states_title_licence_and_provenance():
    md = docs.collection_readme(COLL, 53, "https://example.invalid/A40.html")
    assert md.startswith("# 津波浸水想定データ (A40)")
    assert "`other`" in md
    assert "https://example.invalid/A40.html" in md
    assert "Provenance:" in md
    assert "2016, 2024" in md


def test_collection_agents_counts_from_the_items_not_from_prose():
    md = docs.collection_agents(COLL, ITEMS, "https://example.invalid")
    assert "再配布できる 1" in md and "要確認 1" in md
    assert "1.5 GB" in md
    assert "GML (2)" in md


def test_collection_agents_names_the_columns_a_query_has_to_spell():
    md = docs.collection_agents(COLL, ITEMS)
    assert "`A40_001` 都道府県名" in md
    assert "1 column is coded" in md


def test_collection_agents_lists_only_editorial_relations_with_their_reason():
    md = docs.collection_agents(COLL, ITEMS)
    assert "津波浸水想定域の内と外で避難施設を数える" in md
    assert "測地系が違います" in md
    # The series link is derived from titles, not an editorial judgement, so it
    # does not belong under "often used with".
    assert "mesh500" not in md


def test_collection_agents_survives_a_dataset_with_no_attribute_table():
    bare = {k: v for k, v in COLL.items() if k != "ksj:variants"}
    md = docs.collection_agents(bare, [])
    assert "no 属性情報 table" in md
    assert "size unmeasured" in md


def test_axis_docs_carry_a_licence_line_and_provenance():
    for readme, agents in (
        docs.collections_docs([{"id": "A40"}]),
        docs.regions_docs([{"slug": "39", "count": 356}]),
        docs.licenses_docs([{"status": "allowed", "items": 11538}]),
        docs.license_status_docs("check", "確認が要るもの", [{"count": 8}]),
        docs.categories_docs([{"name": "災害・防災", "count": 15}]),
    ):
        assert readme.startswith("# ")
        assert "Licence:" in readme
        assert "Provenance:" in readme
        assert agents.startswith("# AGENTS.md")


def test_licenses_agents_states_what_check_means():
    _, agents = docs.licenses_docs([
        {"status": "allowed", "items": 3}, {"status": "check", "items": 8},
    ])
    assert "| `check` | 8 |" in agents
    assert "一部制限" in agents


def test_a_single_year_is_not_printed_as_a_range():
    one = {**COLL, "ksj:years": [2012]}
    assert ", 2012." in docs.collection_agents(one, ITEMS)
    assert "2012–2012" not in docs.collection_agents(one, ITEMS)
