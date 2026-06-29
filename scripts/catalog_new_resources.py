from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
RESOURCE_ROOT = ROOT / "storage" / "resources"
TZ = timezone(timedelta(hours=8))

TOKEN_ZH = {
    "ancient": ["古树", "旧时光"],
    "autumn": ["秋天", "岁月", "回忆"],
    "bamboo": ["竹林", "养生", "自然"],
    "bird": ["飞鸟", "远方", "希望"],
    "birds": ["飞鸟", "远方", "希望"],
    "blossom": ["花开", "春天", "希望"],
    "bridge": ["桥", "水乡", "回忆"],
    "canola": ["油菜花", "春天", "希望"],
    "cherry": ["樱花", "春天", "回忆"],
    "cloud": ["云海", "远方", "壮阔"],
    "cottage": ["小屋", "家", "安宁"],
    "couple": ["陪伴", "爱情", "晚年"],
    "courtyard": ["庭院", "老家", "温暖"],
    "daisy": ["雏菊", "简单", "希望"],
    "dew": ["晨露", "清晨", "希望"],
    "dinner": ["晚饭", "团圆", "家人"],
    "dumplings": ["饺子", "团圆", "家人"],
    "family": ["家人", "亲情", "团圆"],
    "field": ["田野", "乡村", "收获"],
    "fish": ["鱼", "家常菜", "丰盛"],
    "flower": ["花", "温柔", "美好"],
    "flowers": ["花", "温柔", "美好"],
    "garden": ["花园", "安宁", "温暖"],
    "ginkgo": ["银杏", "秋天", "岁月"],
    "grass": ["小草", "清新", "希望"],
    "harbor": ["码头", "归来", "生活"],
    "home": ["家", "老家", "烟火气"],
    "house": ["老屋", "家", "回忆"],
    "kitchen": ["厨房", "做饭", "烟火气"],
    "lake": ["湖面", "安静", "人生"],
    "lane": ["老巷", "回忆", "岁月"],
    "lily": ["百合", "思念", "祝福"],
    "lotus": ["荷花", "清净", "安宁"],
    "magnolia": ["玉兰", "春天", "清雅"],
    "maple": ["枫叶", "秋天", "回忆"],
    "meal": ["吃饭", "家常", "温暖"],
    "misty": ["晨雾", "安宁", "回忆"],
    "mountain": ["群山", "远方", "人生"],
    "noodle": ["面条", "热饭", "家"],
    "noodles": ["面条", "热饭", "家"],
    "old": ["老屋", "旧时光", "回忆"],
    "peony": ["牡丹", "富贵", "幸福"],
    "porridge": ["白粥", "早餐", "节俭"],
    "rice": ["米饭", "吃饭", "温饱"],
    "river": ["河边", "水乡", "安宁"],
    "rose": ["玫瑰", "爱情", "温柔"],
    "shelf": ["旧物", "碗柜", "回忆"],
    "spring": ["春天", "希望", "新生"],
    "steam": ["热气", "温暖", "饭菜"],
    "sunbeam": ["光束", "希望", "温暖"],
    "sunlight": ["阳光", "希望", "温暖"],
    "sunrise": ["日出", "清晨", "希望"],
    "sunset": ["夕阳", "人生", "岁月"],
    "tea": ["茶", "养生", "慢生活"],
    "temple": ["寺庙", "祈福", "平安"],
    "tofu": ["豆腐", "节俭", "健康"],
    "tree": ["大树", "守护", "岁月"],
    "village": ["村庄", "老家", "乡愁"],
    "water": ["水乡", "安宁", "回忆"],
    "wheat": ["麦田", "收获", "人生"],
    "window": ["窗边", "等待", "安静"],
}

EMOTION_BY_TOKEN = {
    "sunset": ["reflective", "warm", "life_journey"],
    "sunrise": ["hope", "fresh", "peace"],
    "family": ["family", "warm", "reunion"],
    "dinner": ["family", "warm", "reunion"],
    "kitchen": ["home", "warm", "daily"],
    "tea": ["quiet", "healthy", "nostalgic"],
    "flower": ["gentle", "hope", "warm"],
    "flowers": ["gentle", "hope", "warm"],
    "lotus": ["peace", "hope", "spiritual"],
    "bamboo": ["healing", "peace", "fresh"],
    "temple": ["prayer", "peace", "spiritual"],
    "old": ["nostalgic", "quiet", "memory"],
    "window": ["waiting", "quiet", "hope"],
}


def image_size(path: Path) -> tuple[int, int, float]:
    with Image.open(path) as image:
        width, height = image.size
    return width, height, round(width / height, 4)


def chatgpt_files(folder: Path) -> list[Path]:
    return [
        path
        for path in sorted(folder.iterdir())
        if path.is_file()
        and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
        and path.name.startswith("ChatGPT Image")
    ]


def words_from_slug(slug: str) -> list[str]:
    words: list[str] = []
    for token in slug.split("_"):
        words.extend(TOKEN_ZH.get(token, []))
    seen: set[str] = set()
    return [word for word in words if not (word in seen or seen.add(word))]


def emotions_from_slug(slug: str) -> list[str]:
    emotions: list[str] = []
    for token in slug.split("_"):
        emotions.extend(EMOTION_BY_TOKEN.get(token, []))
    if not emotions:
        emotions = ["quiet", "warm", "memory"]
    seen: set[str] = set()
    return [item for item in emotions if not (item in seen or seen.add(item))][:4]


def asset_from(path: Path, slug: str, title: str, order: int, original: str) -> dict:
    width, height, ratio = image_size(path)
    keywords = words_from_slug(slug)
    return {
        "id": slug,
        "file": path.name,
        "original_file": original,
        "source_order": order,
        "title_zh": title,
        "title_en": slug.replace("_", " "),
        "scene": "_".join(slug.split("_")[1:-1]) if slug.split("_")[-1].isdigit() else "_".join(slug.split("_")[1:]),
        "emotions": emotions_from_slug(slug),
        "keywords_zh": keywords,
        "keywords_en": slug.split("_"),
        "match_text_types": keywords[:6],
        "visual_focus": title,
        "orientation": "portrait" if height >= width else "landscape",
        "width": width,
        "height": height,
        "aspect_ratio": ratio,
        "background_suitability": "good",
        "caption_safe_zone": "center_or_lower_overlay_with_dark_gradient",
    }


def write_index(folder_name: str, template_id: str, name_zh: str, usage: str, entries: list[tuple[str, str]]) -> int:
    folder = RESOURCE_ROOT / folder_name
    files = chatgpt_files(folder)
    if len(files) != len(entries):
        raise RuntimeError(f"{folder_name}: expected {len(entries)} new files, found {len(files)}")
    assets: list[dict] = []
    for order, (source, (slug, title)) in enumerate(zip(files, entries, strict=True), 1):
        original = source.name
        target = folder / f"{slug}{source.suffix.lower()}"
        if source != target:
            if target.exists():
                raise RuntimeError(f"target already exists: {target}")
            source.rename(target)
        assets.append(asset_from(target, slug, title, order, original))
    payload = {
        "schema_version": 1,
        "template_id": template_id,
        "name_zh": name_zh,
        "resource_dir": f"storage/resources/{folder_name}",
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "matching_strategy": {
            "primary": "score segment text against scene, emotions, keywords_zh, keywords_en and match_text_types",
            "usage": usage,
            "tie_breakers": [
                "prefer unused image in the same project",
                "prefer matching emotion",
                "prefer scene diversity across adjacent segments",
            ],
            "language": ["zh-CN", "en"],
        },
        "assets": assets,
    }
    (folder / "index.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(assets)


def append_index(folder_name: str, entries: list[tuple[str, str]]) -> int:
    folder = RESOURCE_ROOT / folder_name
    index_path = folder / "index.json"
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    files = chatgpt_files(folder)
    if len(files) != len(entries):
        raise RuntimeError(f"{folder_name}: expected {len(entries)} new files, found {len(files)}")
    next_order = max(int(item["source_order"]) for item in payload["assets"]) + 1
    for offset, (source, (base_slug, title)) in enumerate(zip(files, entries, strict=True), 0):
        order = next_order + offset
        slug = f"{base_slug}_{order:03d}"
        original = source.name
        target = folder / f"{slug}{source.suffix.lower()}"
        if target.exists():
            raise RuntimeError(f"target already exists: {target}")
        source.rename(target)
        payload["assets"].append(asset_from(target, slug, title, order, original))
    payload["generated_at"] = datetime.now(TZ).isoformat(timespec="seconds")
    index_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(entries)


KITCHEN = [
    ("kitchen_tea_cup_window_sunlight_quiet_001", "窗边茶杯与热气"),
    ("kitchen_teapot_window_old_room_002", "老屋窗边紫砂壶"),
    ("kitchen_noodle_bowl_steam_home_003", "热气腾腾的面条"),
    ("kitchen_steamed_dumplings_bamboo_004", "竹笼蒸饺"),
    ("kitchen_porridge_bowl_breakfast_005", "窗边一碗白粥"),
    ("kitchen_empty_bowl_chopsticks_waiting_006", "空碗与筷子"),
    ("kitchen_old_room_stove_sunlight_007", "阳光里的老厨房"),
    ("kitchen_vegetable_table_harvest_008", "厨房里的新鲜蔬菜"),
    ("kitchen_steamed_buns_bamboo_009", "热蒸包子"),
    ("kitchen_clay_pot_soup_fire_010", "灶火上的砂锅"),
    ("kitchen_home_dishes_table_abundance_011", "满桌家常菜"),
    ("kitchen_rice_bowl_steam_simple_012", "热米饭"),
    ("kitchen_hanging_noodles_courtyard_013", "晾晒的面条"),
    ("kitchen_porridge_table_breakfast_014", "老屋早餐桌"),
    ("kitchen_iron_kettle_tea_leaves_015", "铁壶与茶叶"),
    ("kitchen_chopping_board_vegetables_016", "案板上的青菜"),
    ("kitchen_window_plant_sunlight_017", "厨房窗台的绿植"),
    ("kitchen_old_stove_steamer_018", "老灶台上的蒸笼"),
    ("kitchen_fruit_basket_window_019", "窗边水果篮"),
    ("kitchen_rice_cooker_steam_020", "冒热气的电饭锅"),
    ("kitchen_greens_basket_home_cooking_021", "菜篮里的青菜"),
    ("kitchen_tea_tray_bamboo_quiet_022", "竹影下的茶盘"),
    ("kitchen_empty_table_old_room_023", "老厨房空桌"),
    ("kitchen_steamed_fish_dinner_024", "清蒸鱼"),
    ("kitchen_festive_meal_old_room_025", "节日家宴"),
    ("kitchen_tofu_cutting_board_soybeans_026", "案板上的豆腐"),
    ("kitchen_bowls_shelf_storage_027", "碗柜里的旧碗"),
    ("kitchen_sunlit_window_old_room_028", "洒满阳光的厨房窗"),
    ("kitchen_home_dishes_steamed_buns_029", "包子与家常菜"),
    ("kitchen_family_reunion_dinner_030", "围桌吃饭的一家人"),
]

PLANT = [
    ("plant_lily_pond_sunset_memory_001", "夕阳水边百合"),
    ("plant_peony_garden_sunset_warmth_002", "夕阳牡丹花园"),
    ("plant_lotus_pond_sunset_peace_003", "夕阳荷花池"),
    ("plant_red_camellia_courtyard_joy_004", "庭院红花"),
    ("plant_magnolia_temple_spring_005", "屋檐下的白玉兰"),
    ("plant_magnolia_sunset_blessing_006", "夕阳白玉兰"),
    ("plant_red_peony_sunlight_celebration_007", "阳光里的红牡丹"),
    ("plant_peach_blossom_village_spring_008", "村边桃花"),
    ("plant_canola_field_spring_hope_009", "油菜花田"),
    ("plant_bamboo_forest_sunbeams_healing_010", "竹林晨光"),
    ("plant_tea_leaves_sunrise_health_011", "晨光茶园嫩叶"),
    ("plant_daisy_hillside_sunrise_012", "山坡雏菊"),
    ("plant_lavender_field_sunset_dream_013", "夕阳薰衣草田"),
    ("plant_rose_garden_courtyard_tenderness_014", "庭院玫瑰花丛"),
    ("plant_jasmine_tea_balcony_gentle_015", "茉莉花茶时光"),
    ("plant_maple_leaves_autumn_memory_016", "秋日枫叶落地"),
    ("plant_ginkgo_leaves_autumn_years_017", "阳光银杏叶"),
    ("plant_pine_snow_courtyard_winter_018", "雪后松枝"),
    ("plant_mint_herbs_window_health_019", "窗边薄荷香草"),
    ("plant_ivy_old_alley_growth_020", "爬满藤蔓的老巷"),
    ("plant_dew_grass_sunrise_hope_021", "晨露草地"),
    ("plant_sunflower_field_optimism_022", "向日葵花田"),
    ("plant_orchid_window_gentle_023", "窗边兰花"),
    ("plant_willow_riverside_water_town_024", "水乡垂柳"),
    ("plant_hydrangea_courtyard_memory_025", "庭院绣球花"),
    ("plant_marigold_garden_warmth_026", "暖阳万寿菊"),
    ("plant_white_blossom_branch_spring_027", "春日白花枝头"),
    ("plant_spring_blossom_village_028", "村口春花"),
    ("plant_persimmon_tree_old_village_029", "老村柿子树"),
    ("plant_reeds_lakeside_sunset_reflection_030", "湖边芦苇夕阳"),
    ("plant_moss_stone_wall_years_031", "青苔石墙"),
    ("plant_rose_wall_old_lane_love_032", "老巷玫瑰墙"),
    ("plant_daisy_path_sunset_simple_033", "夕阳小雏菊路"),
    ("plant_iris_flowers_sunset_grace_034", "夕阳鸢尾花"),
    ("plant_morning_glory_wall_hope_035", "墙边牵牛花"),
    ("plant_cherry_blossom_village_spring_036", "村边樱花"),
    ("plant_fallen_petals_stone_lane_memory_037", "落花石板路"),
    ("plant_lotus_leaves_dew_peace_038", "荷叶晨露"),
    ("plant_fern_forest_sunlight_healing_039", "林间蕨叶光"),
    ("plant_tea_plantation_mountains_040", "山间茶园"),
    ("plant_bamboo_stream_quiet_041", "溪边竹影"),
    ("plant_red_maple_courtyard_autumn_042", "庭院红枫"),
    ("plant_cactus_flower_sunset_resilience_043", "夕阳下的仙人掌花"),
    ("plant_ancient_tree_village_shelter_044", "村边古树"),
    ("plant_wildflowers_field_sunset_045", "夕阳野花草地"),
    ("plant_flower_path_sunset_journey_046", "花边乡间小路"),
    ("plant_wheat_field_sunset_harvest_047", "夕阳麦田"),
    ("plant_rice_field_sunset_harvest_048", "夕阳稻田"),
    ("plant_cottage_flower_garden_home_049", "小屋花园"),
]

BROLL = [
    ("broll_village_steps_sunrise_homecoming", "山村石阶日出"),
    ("broll_misty_village_valley_sunrise", "晨雾山村"),
    ("broll_sunbeam_old_lane_memory", "阳光穿过老巷"),
    ("broll_karst_river_sunset_peace", "夕阳山水河面"),
    ("broll_mountain_layers_sunset_reflection", "层峦夕阳"),
    ("broll_birds_sunset_sky_freedom", "飞鸟夕阳天空"),
    ("broll_open_window_sunlight_waiting", "打开的老窗"),
    ("broll_terraced_fields_mist_sunrise", "晨雾梯田"),
    ("broll_lake_sunset_willow_reflection", "柳边湖面夕阳"),
    ("broll_bamboo_path_sunbeams_healing", "竹林光束小路"),
    ("broll_misty_village_road_home", "雾中山村小路"),
    ("broll_fiery_clouds_sunset_years", "火烧云夕阳"),
    ("broll_tea_hills_sunset_health", "夕阳茶山"),
    ("broll_fishing_boat_harbor_sunset_life", "渔船码头夕阳"),
    ("broll_harbor_boats_sunset_busy_life", "夕阳港湾小船"),
    ("broll_peony_village_sunset_warmth", "夕阳村边牡丹"),
    ("broll_old_house_garden_sunset_home", "夕阳老屋花园"),
    ("broll_mountain_stream_valley_journey", "山谷溪流夕阳"),
    ("broll_wheat_field_sunset_harvest", "夕阳麦田"),
    ("broll_lotus_lake_sunset_peace", "荷花湖夕阳"),
    ("broll_village_rooftops_sunrise_memory", "晨光村庄屋顶"),
    ("broll_stone_bridge_water_town_nostalgia", "水乡石桥夕阳"),
    ("broll_cloud_sea_mountains_sunrise", "云海山峰日出"),
    ("broll_field_path_sunset_homecoming", "田边归途小路"),
    ("broll_swallows_village_sunset_blessing", "村口飞燕夕阳"),
    ("broll_temple_gate_sunset_prayer", "古寺门前夕阳"),
    ("broll_river_village_red_sunset_memory", "红霞水乡"),
    ("broll_fence_path_sunset_years", "木栅栏夕阳小路"),
    ("broll_orchard_tree_sunset_harvest", "果树夕阳"),
    ("broll_lakeside_tree_sunset_reflection", "湖边树影夕阳"),
    ("broll_hillside_flowers_sunset_hope", "山坡花路夕阳"),
    ("broll_river_birds_sunset_farewell", "河上归鸟夕阳"),
]


def main() -> None:
    print("bg_kitchen", write_index("bg_kitchen", "kitchen-broll", "厨房烟火气背景图库", "Home cooking, frugality, family meals and warm daily-life emotional segments.", KITCHEN))
    print("bg_plant", write_index("bg_plant", "plant-broll", "植物花园自然疗愈背景图库", "Flowers, seasons, healing nature, hope, memory and quiet emotional segments.", PLANT))
    print("bg_B-Roll_Senior_Emotions", append_index("bg_B-Roll_Senior_Emotions", BROLL))


if __name__ == "__main__":
    main()
