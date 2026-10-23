"""Fake maps for the blind sets: the marker names as the AGV would list them. A case's "map" names one of these and
its "markers" repeats the list, so a checker can hand it to the reader instead of the live map."""

MAPS = {
    "office": ["p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8", "p9", "p10", "home", "exit", "dock2"],
    "expo": ["home", "dock2", "booth_A", "booth_B", "booth_3", "entrance", "stage", "coffee_corner", "info_desk"],
    "korean": ["home", "커피코너", "부스3", "입구", "무대", "안내데스크", "휴게실", "회의실"],
    "hall": ["home", "dock2", "gate_1", "gate_2", "hall_A", "exit", "table_front", "photo_zone", "stage"],
}
MAPS["conference"] = ["home", "dock2", "Main_Stage", "Booth_12", "Registration", "포토존", "라운지", "Coffee_Bar",
                      "Exit_B"]
MAPS["gallery"] = ["home", "dock2", "Gallery_1", "Gallery_2", "Cafe", "기념품점", "화장실_앞", "Elevator"]
MAPS["airport"] = ["Gate_A3", "Gate_B7", "수하물", "Info_Desk", "면세점", "Lounge_2", "home", "dock2"]
