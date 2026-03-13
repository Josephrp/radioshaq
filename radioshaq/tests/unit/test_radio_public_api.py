from __future__ import annotations

import warnings


def test_rigmode_alias_exports_radio_mode_name() -> None:
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always", DeprecationWarning)
        from radioshaq.radio import RigMode, RadioModeName

        # Alias should point to the same object/type.
        assert RigMode is RadioModeName
        # And a DeprecationWarning should have been emitted.
        assert any(isinstance(item.message, DeprecationWarning) for item in w)

