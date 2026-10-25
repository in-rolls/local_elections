"""Splitting a 2016 Karnataka winner cell into name, relation and address."""

import pytest

from local_elections.states.karnataka.parse_tzp import _split


@pytest.mark.parametrize(
    ("cell", "name", "relation"),
    [
        ("ಮಮತ ಎಂ.ಶೆಟ್ಟಿ, ಕೋಂ: ಮೋಹನ್ ದಾಸ್ ಶೆಟ್ಟಿ, ದೇವಸ್ಥ ಬಳಿ", "ಮಮತ ಎಂ.ಶೆಟ್ಟಿ", "ಮೋಹನ್ ದಾಸ್ ಶೆಟ್ಟಿ"),
        ("ಎಂ.ಡಿ.ಸುಧಾ ಕೋಂ.ಎಸ್.ದ್ಯಾವೇಗೌಡ", "ಎಂ.ಡಿ.ಸುಧಾ", "ಎಸ್.ದ್ಯಾವೇಗೌಡ"),
        ("ಪೂರ್ಣಿಮಾ ಗೋಪಾಲ್ ಕೋಂ", "ಪೂರ್ಣಿಮಾ ಗೋಪಾಲ್", ""),
        ("ಓಲೇಕಾರ ಚಂದವ್ವ ಸಂಗಪ್ಪ ಸಾ|| ಚಿನ್ನಾಪೂರ", "ಓಲೇಕಾರ ಚಂದವ್ವ ಸಂಗಪ್ಪ", ""),
        ("ಚಾಂಗುನಾಬಾಯಿ ಮೋಹನ ಸಾ| ಪೋಲಕಪಳ್ಳಿ ತಾಂಡಾ", "ಚಾಂಗುನಾಬಾಯಿ ಮೋಹನ", ""),
        ("ಸುರೇಖಾಗೌಡತಿ ಶಂಕರಗೌಡ ಬಿರೆದಾರ ಸಾಃ ಸುಂಬಡ ತಾಃ ಜೇವಗಿ", "ಸುರೇಖಾಗೌಡತಿ ಶಂಕರಗೌಡ ಬಿರೆದಾರ", ""),
        ("ಪಾಲಪ್ಪ, ಎಂ.ಪಿ.ಪ್ರಕಾಶನಗರ ಹಂಪಿ", "ಪಾಲಪ್ಪ", ""),
        ("ಮಲ್ಲಮ್ಮ ಶಿದ್ರಾಮಪ್ಪ ಯತ್ನಟ್ಟಿ", "ಮಲ್ಲಮ್ಮ ಶಿದ್ರಾಮಪ್ಪ ಯತ್ನಟ್ಟಿ", ""),
    ],
)
def test_the_name_is_split_from_relation_and_address(cell, name, relation):
    got = _split(cell)
    assert got[0] == name
    assert got[1] == relation
