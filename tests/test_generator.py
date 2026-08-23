from data.generate_synthetic_data import build_dataset


def test_generator_creates_minimum_batch_and_noise() -> None:
    rp, bk, ld = build_dataset(n=120, seed=42)

    assert len(rp) == 120
    assert len(bk) >= 120
    assert len(ld) == 120

    # verify at least some noisy patterns exist
    merged = rp.merge(bk, on="reference", suffixes=("_rp", "_bk"), how="inner")
    assert not merged.empty
