"""Pre-seeded curated reading orders."""

from typing import Any

# Each entry matches ReadingOrderRepository.upsert_curated signature:
# slug, name, description, items: list[{issue_title, note}]

CURATED_READING_ORDERS: list[dict[str, Any]] = [
    {
        "slug": "hickman-secret-wars-minimal",
        "name": "Hickman's Secret Wars — Fast Track",
        "description": (
            "89 issues. The fastest path to Secret Wars (2015): "
            "Jonathan Hickman's Avengers and New Avengers runs, then Secret Wars. "
            "Perfect if you want the core saga without side series."
        ),
        "items": [
            {"issue_title": f"Avengers (2012) #{i}"} for i in range(1, 45)
        ] + [
            {"issue_title": f"New Avengers (2013) #{i}"} for i in range(1, 34)
        ] + [
            {"issue_title": "Avengers (2012) #34.1"},
            {"issue_title": "Avengers (2012) #34.2"},
            {"issue_title": "FREE COMIC BOOK DAY 2015 0 (2015)"},
        ] + [
            {"issue_title": f"Secret Wars (2015) #{i}"} for i in range(1, 10)
        ],
    },
    {
        "slug": "hickman-secret-wars-full",
        "name": "Hickman's Secret Wars — Full Saga",
        "description": (
            "219 issues. The complete Jonathan Hickman Marvel run: "
            "Secret Warriors → SHIELD → FF → Fantastic Four → "
            "Avengers → New Avengers → Infinity → Secret Wars. "
            "Read this and Secret Wars will hit like it's supposed to."
        ),
        "items": (
            [{"issue_title": f"Secret Warriors (2009) #{i}"} for i in range(1, 29)]
            + [{"issue_title": "Dark Reign: The List - Secret Warriors (2009) #1"}]
            + [{"issue_title": "Siege: Secret Warriors (2010) #1"}]
            + [{"issue_title": f"S.H.I.E.L.D. (2010) #{i}"} for i in range(1, 7)]
            + [{"issue_title": f"FF (2011) #{i}"} for i in range(1, 12)]
            + [{"issue_title": f"Fantastic Four (1961) #{i}", "note": "Hickman run"} for i in range(570, 589)]
            + [{"issue_title": f"Avengers (2012) #{i}"} for i in range(1, 45)]
            + [{"issue_title": f"New Avengers (2013) #{i}"} for i in range(1, 34)]
            + [{"issue_title": "Avengers (2012) #34.1"}, {"issue_title": "Avengers (2012) #34.2"}]
            + [{"issue_title": f"Infinity (2013) #{i}"} for i in range(1, 7)]
            + [{"issue_title": "FREE COMIC BOOK DAY 2015 0 (2015)"}]
            + [{"issue_title": f"Secret Wars (2015) #{i}"} for i in range(1, 10)]
        ),
    },
    {
        "slug": "age-of-ultron",
        "name": "Age of Ultron",
        "description": (
            "Brian Michael Bendis's Age of Ultron event (2013). "
            "10 issues plus the key tie-ins."
        ),
        "items": [
            {"issue_title": f"Age of Ultron (2013) #{i}"} for i in range(1, 11)
        ] + [
            {"issue_title": "Wolverine and the X-Men (2011) #27AU"},
            {"issue_title": "Uncanny Avengers (2012) #8AU"},
            {"issue_title": "Superior Spider-Man (2013) #6AU"},
        ],
    },
    {
        "slug": "civil-war-2006",
        "name": "Civil War (2006)",
        "description": (
            "Mark Millar's original Civil War event. "
            "The 7-issue core series plus key tie-ins."
        ),
        "items": [
            {"issue_title": f"Civil War (2006) #{i}"} for i in range(1, 8)
        ] + [
            {"issue_title": "Civil War: Frontline (2006) #1", "note": "Key tie-in"},
            {"issue_title": "Amazing Spider-Man (1999) #532", "note": "Spider-Man unmasked"},
            {"issue_title": "Amazing Spider-Man (1999) #533"},
            {"issue_title": "Amazing Spider-Man (1999) #534"},
            {"issue_title": "Amazing Spider-Man (1999) #535"},
            {"issue_title": "Captain America (2004) #22"},
            {"issue_title": "Captain America (2004) #23"},
            {"issue_title": "Captain America (2004) #24"},
            {"issue_title": "Captain America (2004) #25"},
        ],
    },
    {
        "slug": "house-of-x-powers-of-x",
        "name": "House of X / Powers of X",
        "description": (
            "Jonathan Hickman's X-Men relaunch (2019). "
            "Read these 12 issues in alternating order for the full effect. "
            "HoX #1 → PoX #1 → HoX #2 → PoX #2 → ..."
        ),
        "items": [
            {"issue_title": "House of X (2019) #1"},
            {"issue_title": "Powers of X (2019) #1"},
            {"issue_title": "House of X (2019) #2"},
            {"issue_title": "Powers of X (2019) #2"},
            {"issue_title": "House of X (2019) #3"},
            {"issue_title": "Powers of X (2019) #3"},
            {"issue_title": "House of X (2019) #4"},
            {"issue_title": "Powers of X (2019) #4"},
            {"issue_title": "House of X (2019) #5"},
            {"issue_title": "Powers of X (2019) #5"},
            {"issue_title": "House of X (2019) #6"},
            {"issue_title": "Powers of X (2019) #6"},
        ],
    },
    {
        "slug": "infinity-gauntlet",
        "name": "Infinity Gauntlet (1991)",
        "description": (
            "Jim Starlin's classic Infinity Gauntlet saga. "
            "Start with the Silver Surfer issues for context, then the main event."
        ),
        "items": [
            {"issue_title": "Silver Surfer (1987) #34", "note": "Thanos returns"},
            {"issue_title": "Silver Surfer (1987) #35"},
            {"issue_title": "Silver Surfer (1987) #36"},
            {"issue_title": "Thanos Quest (1990) #1"},
            {"issue_title": "Thanos Quest (1990) #2"},
        ] + [
            {"issue_title": f"Infinity Gauntlet (1991) #{i}"} for i in range(1, 7)
        ],
    },
]
