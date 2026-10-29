import json

from onboarding.generator import DATA_DIR, PRACTICES, generate


def test_regenerating_matches_committed_data(tmp_path):
    generate(tmp_path, seed=7)
    for spec in PRACTICES:
        for f in (tmp_path / spec["id"]).iterdir():
            committed = (DATA_DIR / spec["id"] / f.name).read_text(encoding="utf-8")
            assert f.read_text(encoding="utf-8") == committed, f"{spec['id']}/{f.name} is stale; rerun the generator"


def test_defect_counts():
    counts = {}
    for spec in PRACTICES:
        truth = json.loads((DATA_DIR / spec["id"] / "defects.json").read_text(encoding="utf-8"))["defects"]
        counts[spec["id"]] = len(truth)
    assert sum(counts.values()) == 30
    assert sorted(counts.values())[0] == 0  # one clean practice
    assert all(3 <= n <= 8 for n in counts.values() if n)


def test_packet_shape():
    for spec in PRACTICES:
        folder = DATA_DIR / spec["id"]
        providers = (folder / "providers.csv").read_text(encoding="utf-8").strip().splitlines()[1:]
        assert 3 <= len(providers) <= 12
        rules = [l for l in (folder / "protocols.md").read_text(encoding="utf-8").splitlines() if l.startswith("- ")]
        assert 5 <= len(rules) <= 15
        assert len(json.loads((folder / "smoke_tests.json").read_text(encoding="utf-8"))) == 10
