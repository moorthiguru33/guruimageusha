"""
generate_prompts.py — Smart Multi-Variation Prompt Generator
=============================================================
Target:
  • Common items  : 20+ images each  (10 base × ×2 pipeline)
  • Hero items    : 50+ images each  (25 base × ×2 pipeline)
  • Fish          : 70 total items
  • FLUX.2 Klein  : Natural sentences, 45-80 words, no neg prompts
Run:
  python3 generate_prompts.py
"""

import json, random
from pathlib import Path
from itertools import product
random.seed(42)

_BG = ("isolated on solid plain light grey background, "
       "NOT black background, NOT white background, grey studio backdrop, "
       "no shadows on background, clean crisp edges")

BASE = (f"{_BG}, professional studio product photography, "
        "Canon EOS R5 100mm macro lens, f8 aperture, "
        "8k ultra high definition, ultra realistic, photorealistic, "
        "true-to-life color, razor sharp focus, softbox studio lighting, "
        "centered composition, commercial product photography quality")

FOOD_BASE = (f"{_BG}, professional studio food photography, "
             "Canon EOS R5 50mm lens, f5.6 aperture, "
             "8k ultra high definition, ultra realistic, photorealistic, "
             "accurate food color and texture, razor sharp focus, "
             "softbox studio lighting, appetizing presentation, "
             "centered composition, commercial food photography quality")

ANIMAL_BASE = (f"{_BG}, professional studio animal photography, "
               "Canon EOS R5 200mm telephoto lens, f4 aperture, "
               "8k ultra high definition, ultra realistic, photorealistic, "
               "correct species anatomy, true-to-life, no fantasy elements, "
               "fur and feather strand detail, catchlight in eyes, "
               "softbox studio lighting, centered composition, wildlife documentary quality")

VIEWS_ALL   = ["front view","side profile view","45 degree angle view",
               "top view overhead","low angle hero shot","close-up macro detail view"]
VIEWS_FOOD  = ["front view eye level","45 degree angle view",
               "top view overhead flat lay","low angle hero shot",
               "close-up macro detail view","three-quarter angle view"]
VIEWS_STD   = ["front view","side profile view","45 degree angle view",
               "top view overhead","close-up macro detail view"]
VIEWS_3     = ["front view","45 degree angle view","top view overhead"]
VIEWS_FLOWER= ["front view","45 degree angle view","close-up macro view",
               "top view overhead","side profile view"]

def _item(cat, sub, prompt):
    return {"category":cat,"subcategory":sub,"prompt":prompt,
            "seed":random.randint(10000,999999),"index":0,
            "filename":"img_000000.png","status":"pending"}

# 10 diverse views for auto-boost
_VIEWS10 = [
    "front view", "side profile view", "45 degree angle view",
    "top view overhead", "close-up macro detail view",
    "low angle hero shot", "three-quarter angle view",
    "45 degree right angled view", "front close-up view", "overhead angled view",
]

_BAD_DESC_STARTS = ("from side","from above","from the","front view","side view",
                    "top view","45 degree","close-up","low angle","three-quarter")

def _clean_descs(descriptions):
    """Remove descriptions that are just view directions (common mistake in data)."""
    clean = [d for d in descriptions
             if len(d.split()) > 4
             and not d.strip().lower().startswith(_BAD_DESC_STARTS)]
    return clean if clean else [descriptions[0]]

def expand_standard(cat, sub, descriptions, views=VIEWS_STD, suffix=BASE):
    """Auto-boost to always produce ≥10 base prompts per subcategory."""
    descs = _clean_descs(descriptions)
    working_views = list(views)
    extra = [v for v in _VIEWS10 if v not in working_views]
    ei = 0
    while len(descs) * len(working_views) < 10 and ei < len(extra):
        working_views.append(extra[ei]); ei += 1
    items = []
    for desc, view in product(descs, working_views):
        items.append(_item(cat, sub, f"A single {desc}, {view}, {suffix}"))
    return dedup(items)

def expand_hero(cat, sub, descriptions, contexts, views=VIEWS_FOOD, suffix=FOOD_BASE):
    items = []
    for desc, view in product(descriptions, views):
        items.append(_item(cat, sub, f"A single serving of {desc}, {view}, {suffix}"))
    for ctx, view in product(contexts, views[:3]):
        items.append(_item(cat, sub, f"A single {ctx}, {view}, {suffix}"))
    return dedup(items)

def expand_food(cat, sub, descriptions, views=VIEWS_FOOD, suffix=FOOD_BASE):
    """Auto-boost to always produce ≥10 base prompts per subcategory."""
    descs = _clean_descs(descriptions)
    working_views = list(views)
    extra_food = ["front view eye level","45 degree angle view","top view overhead flat lay",
                  "low angle hero shot","close-up macro detail view","three-quarter angle view",
                  "side profile view","overhead birds eye view","45 degree left angle view","front close view"]
    ei = 0
    while len(descs) * len(working_views) < 10:
        v = extra_food[ei % len(extra_food)]
        if v not in working_views: working_views.append(v)
        ei += 1
        if ei > 20: break
    items = []
    for desc, view in product(descs, working_views):
        items.append(_item(cat, sub, f"A single serving of {desc}, {view}, {suffix}"))
    return dedup(items)

def dedup(items):
    seen, out = set(), []
    for i in items:
        if i["prompt"] not in seen:
            seen.add(i["prompt"]); out.append(i)
    return out

# ══════════════════════════════════════════════════
# 1. FOOD INDIAN
# ══════════════════════════════════════════════════
def food_indian():
    items = []
    # BIRYANI HERO
    bir_d = ["Chicken Biryani with whole chicken leg piece, long grain saffron basmati rice, fried onions on top, served in a round stainless steel plate",
             "Chicken Biryani with bone-in chicken pieces and golden saffron rice, garnished with fresh mint leaves, served in a copper handi pot",
             "Chicken Biryani with juicy chicken drumstick and aromatic basmati rice, served on a banana leaf",
             "Hyderabadi Dum Biryani with juicy chicken and long grain rice, served in a round steel thali with raita on side",
             "Mutton Biryani with tender mutton pieces and aromatic basmati rice, garnished with caramelized onions, served in a wide ceramic bowl",
             "Vegetable Biryani with colorful mixed vegetables and fragrant basmati rice, served on a round plate",
             "Egg Biryani with halved boiled eggs and saffron rice, served in a clay pot",
             "Prawns Biryani with large prawns and basmati rice, served in a wide steel bowl"]
    bir_c = ["Chicken Biryani with rice and chicken leg, served in a deep round steel bowl with a spoon",
             "Chicken Biryani plated with raita and sliced onion salad on the side, full meal spread",
             "Chicken Biryani served in a dark clay pot with lid beside it",
             "Chicken Biryani freshly scooped onto a banana leaf",
             "open copper biryani handi pot filled with steaming Chicken Biryani"]
    items += expand_hero("food_indian","biryani", bir_d, bir_c, VIEWS_FOOD, FOOD_BASE)
    # DOSA HERO
    dosa_d = ["crispy plain dosa folded in a half-moon shape, golden brown, served on a round stainless steel plate",
              "Masala dosa filled with spiced potato masala, crispy golden, served on a banana leaf with sambar and coconut chutney",
              "Ghee roast dosa with shiny butter coating, deep golden, served on a round ceramic plate",
              "Rava dosa with lacy crispy texture and onion topping, served on a stainless steel plate",
              "Paper thin extra-long paper dosa, crispy and light, served on a large tray",
              "Set dosa soft fluffy stack of three pieces, served with sambar and coconut chutney on the side",
              "Onion dosa with diced onions embedded in crispy batter, golden brown",
              "Cheese dosa with melted cheese inside, golden crispy, served on a plate"]
    dosa_c = ["plain dosa golden crispy with a small bowl of coconut chutney and sambar on the side",
              "Masala dosa served on a banana leaf with three chutneys",
              "Ghee roast dosa glistening with butter on a round steel plate",
              "thin crispy dosa with visible golden bubbles on surface",
              "dosa being served hot from a cast iron tawa"]
    items += expand_hero("food_indian","dosa", dosa_d, dosa_c, VIEWS_FOOD, FOOD_BASE)
    # VADA HERO
    vada_d = ["Medu vada with perfect donut shape, crispy surface, golden brown, served on a stainless steel plate with coconut chutney",
              "Medu vada with crispy golden exterior and soft interior, served on a banana leaf",
              "Masala vada crispy and round, deep fried golden brown, served on a banana leaf",
              "Sambar vada soaked in hot sambar broth, soft, served in a bowl",
              "Dahi vada with white yogurt covering, garnished with tamarind chutney and sev on top",
              "Crispy Medu vada with hole in center, served on a round plate with green chutney"]
    vada_c = ["two Medu vadas stacked on a plate with coconut chutney",
              "Medu vada with visible crispy outer ring and soft interior cross-section",
              "Vada served in a steel tiffin with sambar in a small bowl"]
    items += expand_hero("food_indian","vada_single", vada_d, vada_c, VIEWS_FOOD, FOOD_BASE)
    for v in VIEWS_FOOD[:4]:
        items.append(_item("food_indian","vada_group",
            f"A group of 6 Medu vadas with perfect donut shapes, crispy golden brown, "
            f"arranged in a circle on a round steel plate, {v}, {FOOD_BASE}"))
    # Other dishes
    other = {
        "idli":["soft white idli pair served on a round plate with sambar","soft white idli with coconut chutney and sambar on a banana leaf","fluffy round white idli served with green and red chutney"],
        "samosa":["crispy triangular samosa with golden pastry, served on a white plate with green chutney","freshly fried golden samosa on a plate","samosa cut in half showing potato and pea filling inside"],
        "uttapam":["thick soft uttapam with diced onion and tomato topping, served on a steel plate","onion tomato uttapam on a cast iron tawa golden base","mixed vegetable uttapam thick soft pancake on a plate"],
        "appam":["lacy white appam with crispy edges and soft center, served on a banana leaf","soft appam with egg in center, cooked in a round appam pan","plain white appam served with coconut milk in a small bowl"],
        "upma":["fluffy semolina rava upma garnished with curry leaves, mustard seeds, and cashews in a bowl","white rava upma with vegetables in a round ceramic bowl","upma with green peas and carrot mix in a steel bowl"],
        "pongal":["creamy white ven pongal with ghee, whole peppercorns, cashews, served in a round steel bowl","ven pongal with ghee poured on top in a banana leaf","sweet pongal with jaggery and raisins in a clay bowl"],
        "chole_bhature":["fluffy deep fried bhature bread with spicy dark chole curry on a round plate","two puffy bhature with a bowl of chole on the side","chole bhature with sliced onion and green chili on the side"],
        "dal_makhani":["creamy dark dal makhani with butter and cream swirl on top, served in a clay pot","black dal makhani in a round steel bowl with bread on the side","dal makhani with fresh cream and coriander garnish in a ceramic bowl"],
        "palak_paneer":["green creamy palak paneer curry with white paneer cubes, served in a steel bowl","thick spinach palak paneer in a ceramic serving bowl with cream on top","palak paneer with large paneer chunks in green gravy in a clay pot"],
        "butter_chicken":["rich orange butter chicken curry with tender chicken pieces, served in a steel bowl","butter chicken murgh makhani with cream swirl on top in a ceramic bowl","butter chicken with naan bread on the side in a round plate"],
        "chicken_65":["deep fried spicy chicken 65 pieces garnished with curry leaves and green chili on a plate","chicken 65 red spiced crispy pieces in a round ceramic bowl","chicken 65 with lemon wedge and sliced onion rings on a plate"],
        "chicken_tikka":["grilled chicken tikka pieces with char marks, served with sliced onion rings on a plate","orange marinated chicken tikka skewers on a metal plate","chicken tikka with mint chutney and lemon on the side"],
        "fish_curry":["spicy red fish curry with whole fish pieces in a clay pot","Kerala style fish curry in a dark clay chatti pot","Goa style fish curry with coconut milk gravy in a bowl"],
        "fish_fry":["crispy golden spice crusted fish fry served on a banana leaf","Tawa fish fry with masala coating, served on a plate with lemon","crispy fried fish pieces garnished with onion rings"],
        "rasam":["thin tangy tomato rasam in a round steel tumbler cup","South Indian rasam in a steel cup with tamarind aroma","spiced pepper rasam in a glass tumbler with curry leaves"],
        "sambhar":["thick orange vegetable sambhar in a round steel bowl with drumstick pieces","South Indian sambhar with vegetables in a clay bowl","sambhar with floating vegetable pieces in a wide steel bowl"],
        "payasam":["creamy white semiya payasam with cashews and raisins, served in a steel bowl","rice kheer payasam with saffron and cardamom in a glass bowl","vermicelli payasam in a round silver bowl"],
        "halwa":["golden glossy sooji halwa garnished with saffron and almonds in a steel bowl","shiny carrot gajar halwa with ghee and cashews in a round bowl","moong dal halwa with ghee and dry fruits in a serving bowl"],
        "poha":["fluffy yellow poha with diced onion and peanuts garnished with coriander in a plate","Indore style poha with sev and pomegranate topping in a bowl","beaten rice poha with mustard seeds and curry leaves in a steel plate"],
        "paratha":["layered whole wheat paratha with golden spots, served with white curd and pickle","Aloo paratha stuffed with spiced potato, served with butter on top","flaky Punjabi paratha on a tawa with ghee drizzle"],
        "naan":["soft white garlic naan bread with butter and garlic, served on a clay plate","tandoor baked naan with black spots, served with butter","soft leavened naan bread on a round plate with coriander garnish"],
        "pakoda":["crispy golden onion pakoda bhaji served in a paper cone with chutney","assorted pakoda fritters in a clay bowl","mirchi bajji green chili pakoda on a banana leaf"],
        "prawn_masala":["spicy red prawn masala with shell-on prawns in a thick gravy, served in a bowl","Kerala prawn masala with coconut gravy in a clay pot","Goan prawn curry with tangy sauce in a serving bowl"],
        "egg_masala":["spicy egg masala curry with halved boiled eggs in red gravy, served in a bowl","egg masala with two halved eggs on a steel plate","Chettinad egg curry with whole eggs in dark spicy gravy"],
        "curd_rice":["white curd rice with mustard seeds, curry leaves, and pomegranate garnish in a bowl","South Indian thayir sadam in a round steel plate","curd rice with grated carrot and coriander in a ceramic bowl"],
        "lemon_rice":["yellow lemon rice with peanuts and curry leaves in a round plate","South Indian lemon rice with mustard seeds and peanuts","chitranna lemon rice in a banana leaf"],
        "puttu":["cylindrical steamed puttu rice cake with coconut layers, served on a round plate","puttu with banana and papadam on the side","Kerala puttu with kadala curry in a banana leaf"],
    }
    for sub, descs in other.items():
        items += expand_food("food_indian", sub, descs, VIEWS_FOOD[:4], FOOD_BASE)
    return dedup(items)

# ══════════════════════════════════════════════════
# 2. BROILER CHICKEN HERO
# ══════════════════════════════════════════════════
def poultry_chicken():
    items = []
    live_d = ["live white broiler chicken standing naturally, plump white feathers, red comb and wattle, correct poultry anatomy, full body",
              "live white broiler chicken sitting, round plump body, white fluffy feathers, full body",
              "live white broiler chicken walking, healthy plump white bird, full body",
              "live white broiler chicken with red comb, white feathers, alert eyes, full body portrait",
              "healthy white broiler chicken, clean white feathers, large plump breast, full body",
              "white broiler chicken, plump commercial breed, short yellow beak, full body"]
    live_c = ["white broiler chicken plump and healthy, round body, white feathers, red comb, natural standing pose",
              "single white broiler chicken full body, accurate poultry anatomy, no fantasy",
              "large white broiler chicken, commercial breed, plump breast"]
    items += expand_hero("poultry_chicken","broiler_live", live_d, live_c, VIEWS_ALL, ANIMAL_BASE)
    items += expand_standard("poultry_chicken","raw_whole_chicken",
        ["whole raw broiler chicken cleaned, pale yellow-white skin, full body",
         "whole raw chicken with skin, fresh pink-white color, ready for cooking",
         "fresh whole raw chicken on a white plate, uncooked pale skin"], VIEWS_STD, BASE)
    items += expand_standard("poultry_chicken","country_hen",
        ["live Indian country hen, brown and black feathers, red comb, full body",
         "desi country chicken, multicolored brown plumage, red wattle, full body",
         "country chicken hen standing, speckled feathers, alert, full body"], VIEWS_STD, ANIMAL_BASE)
    items += expand_standard("poultry_chicken","rooster",
        ["colorful rooster with bright red comb, multicolored feathers, tall tail feathers, full body",
         "Indian rooster crowing, red comb raised, colorful plumage, full body",
         "rooster with iridescent green-black tail feathers and red comb, full body"], VIEWS_STD, ANIMAL_BASE)
    return dedup(items)

# ══════════════════════════════════════════════════
# 3. FISH & SEAFOOD — 70 total
# ══════════════════════════════════════════════════
def fish_seafood():
    items = []
    fish_list = [
        ("rohu","Rohu fish, silver-grey scales, Indian river carp, correct anatomy, full body"),
        ("katla","Katla fish, large silver scales, fresh Indian carp, full body"),
        ("pomfret_s","Silver Pomfret fish, flat round body, silver sheen, full body"),
        ("pomfret_b","Black Pomfret fish, dark grey flat round body, full body"),
        ("kingfish","King fish Surmai, elongated silver-grey streamlined body, full body"),
        ("seer_fish","Seer fish Vanjaram, silver body with faint vertical bands, full body"),
        ("salmon","Atlantic Salmon, pink-orange flesh, silver spotted skin, full body"),
        ("tuna","Yellowfin Tuna, dark blue back, silver belly, full body"),
        ("tilapia","Tilapia, silver-grey scales, compressed oval body, full body"),
        ("snapper","Red Snapper, bright red-pink skin, white belly, full body"),
        ("hilsa","Hilsa Ilish, shiny silver scales, forked tail, full body"),
        ("mackerel","Indian Mackerel, blue-green striped back, silver belly, full body"),
        ("sardine","Fresh sardine, silver scales, blue-green back, full body"),
        ("catfish","Catfish, smooth grey-brown skin, long barbel whiskers, full body"),
        ("sole","Sole fish, flat oval body, brown skin, full body"),
        ("sea_bass","Sea bass, silver body, black lateral line, full body"),
        ("carp","Common carp, large golden-bronze scales, full body"),
        ("anchovy","Anchovy fish, small silver body, greenish back, full body"),
        ("trout","Rainbow trout, pink lateral stripe, spotted skin, full body"),
        ("red_mullet","Red mullet, reddish-pink skin, two chin barbels, full body"),
        ("prawn_tiger","Tiger prawn, orange and black striped shell, full body"),
        ("prawn_white","White shrimp, transparent grey-white shell, full body"),
        ("crab_blue","Blue swimmer crab, blue-green shell, large claws, full body"),
        ("crab_mud","Mud crab, dark brown shell, powerful large claws, full body"),
        ("squid","Squid, white-cream tube body, purple-spotted tentacles, full body"),
        ("lobster_raw","Whole raw lobster, dark greenish-black shell, claws extended, full body"),
        ("lobster_red","Cooked lobster, bright red shell, claws, full body"),
        ("oyster","Fresh oyster on half shell, glistening grey flesh"),
        ("mussel","Blue mussel, dark oval shell slightly opened"),
        ("clam","Fresh clam, ribbed white-grey oval shell, full body"),
    ]
    fish_views = [
        "front view", "side profile view",
        "45 degree angle view", "top view overhead",
        "close-up macro detail view",
    ]
    for sub, det in fish_list:
        for v in fish_views[:2]:   # 2 views × 30 species = 60, +10 groups = 70 total
            items.append(_item("fish_seafood", sub,
                f"A single {det}, accurately shaped, correct species, {v}, {ANIMAL_BASE}"))
    group_prompts = [
        f"A group of 6 assorted fresh fish arranged in a row on a tray, {FOOD_BASE}",
        f"A pile of fresh tiger prawns arranged on a steel tray, top view overhead, {FOOD_BASE}",
        f"A group of 4 fresh crabs with claws on a dark slate board, top view, {FOOD_BASE}",
        f"A display of assorted fresh seafood with fish, prawns and crabs, top view, {FOOD_BASE}",
        f"A single fresh whole pomfret on a white plate with lemon, front view, {FOOD_BASE}",
        f"A pile of fresh sardines on a banana leaf, top view, {FOOD_BASE}",
        f"A single whole raw salmon with pink flesh and silver skin, side profile view, {ANIMAL_BASE}",
        f"A group of 8 fresh prawns in a circular pattern on a round plate, top view, {FOOD_BASE}",
        f"A single fresh lobster with dark shell and extended claws, front view, {ANIMAL_BASE}",
        f"A single fresh squid with white body and tentacles spread, top view overhead, {ANIMAL_BASE}",
    ]
    for i, pr in enumerate(group_prompts):
        items.append(_item("fish_seafood", f"seafood_group_{i+1}", pr))
    return dedup(items)[:70]

# ══════════════════════════════════════════════════
# 4. FLOWERS
# ══════════════════════════════════════════════════
def flowers():
    items = []
    fl_suf = (f"{_BG}, professional studio floral photography, Canon EOS R5 macro lens, "
              "8k ultra realistic, sharp petal detail, true-to-life color, centered composition")
    # Rose hero
    rose_d = ["deep red rose in full bloom with velvety petals and dew drops, green stem with thorns",
              "red rose bud half open, showing tight inner petals, green stem",
              "fully open red rose flower showing layered petals, green leaves visible",
              "dark red rose with water droplets on petals, beautiful bloom",
              "red rose closeup showing petal texture and natural color gradient",
              "fresh red rose with long green thorny stem, perfect bloom",
              "red rose from above showing spiral petal arrangement",
              "red rose head only without stem, full bloom, centered"]
    rose_c = ["single red rose flower, full bloom, velvety petals, true-to-life red color",
              "single red rose with dewdrops, romantic, sharp petal detail",
              "single red rose, professional floral photography, grey background"]
    items += expand_hero("flowers","rose_red", rose_d, rose_c, VIEWS_FLOWER, fl_suf)
    # Other roses
    for sub, color, detail in [
        ("rose_pink","pink","soft pink petals, delicate full bloom"),
        ("rose_white","white","pure white petals, elegant clean bloom"),
        ("rose_yellow","yellow","bright yellow petals, cheerful full bloom"),
        ("rose_orange","orange","warm orange petals, vibrant full bloom"),
        ("rose_dark_red","dark crimson red","velvety deep red petals, romantic bloom"),
    ]:
        items += expand_standard("flowers", sub, [
            f"single {color} rose in full bloom, {detail}, green stem with leaves",
            f"single {color} rose bud, {detail}, fresh and perfect",
            f"single {color} rose closeup, {detail}, sharp petal detail",
        ], VIEWS_FLOWER, fl_suf)
    # Rose groups
    for v in VIEWS_FLOWER[:3]:
        items.append(_item("flowers","rose_bouquet_red",
            f"A bouquet of 12 deep red roses in full bloom, tightly arranged, green leaves, {v}, {fl_suf}"))
        items.append(_item("flowers","rose_group_mixed",
            f"A group of 8 roses in mixed colors red, pink, yellow and white, arranged naturally, {v}, {fl_suf}"))
    # Other flowers
    flower_items = [
        ("lotus_pink","pink lotus",[
            "pink lotus flower in full bloom with layered petals and yellow center",
            "pink lotus half open, showing inner petals",
            "pink lotus flower head, full bloom, correct lotus anatomy"]),
        ("lotus_white","white lotus",[
            "white lotus flower in full bloom, pure white petals, golden center",
            "white lotus bud about to open, green sepals visible",
            "white lotus full bloom from above showing petal arrangement"]),
        ("jasmine","jasmine",[
            "jasmine flowers, small white five-petaled flowers on a green stem",
            "white jasmine flower cluster, fragrant, small delicate petals",
            "jasmine flower in full bloom, white petals with yellow center"]),
        ("marigold_orange","orange marigold",[
            "bright orange marigold in full round bloom with layered petals",
            "orange marigold closeup showing petal texture, round pompom shape",
            "orange marigold with green stem and leaves, full bloom"]),
        ("marigold_yellow","yellow marigold",[
            "bright yellow marigold in full round bloom, layered petals",
            "yellow marigold closeup showing round pompom shape",
            "yellow marigold with green stem, full bloom"]),
        ("sunflower","sunflower",[
            "large sunflower with bright yellow petals and dark brown center, tall green stem",
            "sunflower head from front showing yellow ray petals and disc",
            "sunflower closeup showing seed pattern in brown center"]),
        ("lily_white","white lily",[
            "white lily trumpet-shaped flower with yellow stamens, green stem",
            "white lily in full bloom showing six petals and stamens",
            "white lily bud and open flower on same stem"]),
        ("lily_pink","pink lily",[
            "pink lily trumpet-shaped flower with orange stamens, green stem",
            "pink lily in full bloom showing spotted petals",
            "pink lily closeup showing petal texture and stamens"]),
        ("orchid_purple","purple orchid",[
            "purple orchid with intricate center pattern, five petals",
            "orchid spray with multiple purple flowers on arching stem",
            "single purple orchid bloom showing complex lip structure"]),
        ("orchid_white","white orchid",[
            "white orchid phalaenopsis with yellow center, elegant, five petals",
            "white orchid spray with multiple blooms on stem",
            "white orchid from above showing petal arrangement"]),
        ("hibiscus_red","red hibiscus",[
            "large red hibiscus with five wide petals and prominent yellow stamen",
            "red hibiscus in full bloom, tropical flower, green calyx visible",
            "red hibiscus closeup showing stamen column detail"]),
        ("chrysanthemum","yellow chrysanthemum",[
            "round yellow chrysanthemum pompom in full bloom",
            "yellow chrysanthemum showing tightly packed petals",
            "yellow mum flower head from above showing spiral pattern"]),
        ("gerbera_orange","orange gerbera daisy",[
            "large orange gerbera daisy with flat petals around dark center",
            "orange gerbera closeup showing petal and center detail",
            "orange gerbera with green stem, bright color"]),
        ("tulip_red","red tulip",[
            "cup-shaped red tulip in bloom, smooth petals, green stem",
            "red tulip bud about to open, pointed top, green stem",
            "red tulip from above showing petal arrangement"]),
        ("lavender","lavender",[
            "lavender sprig with small purple flowers on grey-green stem",
            "bunch of lavender stalks, purple flowers, aromatic",
            "lavender flower closeup showing tiny purple florets"]),
        ("daisy_white","white daisy",[
            "white daisy with white ray petals and bright yellow center",
            "white daisy closeup showing petal arrangement and center",
            "white daisy with green stem, simple and fresh"]),
        ("bougainvillea","pink bougainvillea",[
            "bright magenta pink bougainvillea with paper-thin bracts",
            "bougainvillea cluster with pink-purple papery bracts",
            "bougainvillea branch with multiple pink flowers"]),
    ]
    for sub, name, descs in flower_items:
        items += expand_standard("flowers", sub, descs, VIEWS_FLOWER, fl_suf)
    for v in VIEWS_FLOWER[:3]:
        items.append(_item("flowers","marigold_garland",
            f"A fresh marigold garland with orange and yellow flowers, traditional Indian style, {v}, {fl_suf}"))
        items.append(_item("flowers","mixed_bouquet",
            f"A beautiful mixed flower bouquet with roses, marigolds and jasmine, colorful, naturally arranged, {v}, {fl_suf}"))
        items.append(_item("flowers","jasmine_garland",
            f"A white jasmine flower garland, white flowers strung on thread, traditional Indian mala, {v}, {fl_suf}"))
    return dedup(items)

# ══════════════════════════════════════════════════
# 5. FRUITS
# ══════════════════════════════════════════════════
def fruits():
    items = []
    fr_suf = (f"{_BG}, professional studio product photography, Canon EOS R5, "
              "8k ultra realistic, accurate fruit shape, true-to-life color, sharp detail, centered composition")
    hero = {
        "apple_red":("red apple",[
            "shiny red apple, round shape, smooth skin with natural color gradient",
            "red apple with green leaf on stem, fresh and ripe",
            "red apple with water droplets on skin, fresh",
            "red apple cut in half showing white flesh and seeds",
            "red apple from above showing stem and skin texture"]),
        "mango":("ripe yellow-orange mango",[
            "ripe Alphonso mango, plump oval, yellow-orange skin, fresh",
            "ripe mango with yellow skin and slight blush, full body",
            "ripe mango showing yellow color gradient, natural skin texture",
            "mango with stem and leaf attached, ripe golden yellow",
            "mango cut in half showing golden-orange flesh inside"]),
        "banana":("ripe yellow banana",[
            "ripe yellow banana, curved, bright yellow skin, unblemished",
            "bunch of ripe yellow bananas, five fingers together",
            "single ripe banana with brown spots, naturally ripe",
            "yellow banana from above showing curved shape",
            "banana with peel partially opened"]),
        "orange":("fresh orange",[
            "round orange, bright orange peel with dimpled natural texture",
            "orange with green leaf on stem, fresh and ripe",
            "orange cut in half showing juicy segments inside",
            "orange from above showing navel end and peel texture",
            "orange with water droplets, fresh"]),
        "grapes_black":("bunch of black grapes",[
            "large bunch of round dark purple-black seedless grapes on stem",
            "black grapes closeup showing individual round berries",
            "bunch of black grapes from above, full cluster",
            "black grapes with green leaf, fresh"]),
        "grapes_green":("bunch of green grapes",[
            "large bunch of round seedless green grapes on stem, translucent",
            "green grapes closeup showing individual round berries",
            "bunch of green grapes from above, full cluster",
            "green grapes with dew drops, fresh and plump"]),
    }
    for sub,(name,descs) in hero.items():
        items += expand_standard("fruits", sub, descs, VIEWS_STD, fr_suf)
    std = [
        ("watermelon_whole","whole watermelon",[
            "whole watermelon, large oval, dark green with lighter stripes",
            "whole watermelon from side showing green striped skin",
            "whole watermelon from above showing oval shape"]),
        ("watermelon_slice","watermelon slice",[
            "triangular watermelon slice with bright red flesh and black seeds",
            "watermelon slice showing juicy red interior",
            "round watermelon cross-section showing red flesh"]),
        ("pineapple","whole pineapple",[
            "whole pineapple with green crown leaves and rough yellow-brown skin",
            "pineapple from side showing full body and crown",
            "pineapple from above showing crown leaf arrangement"]),
        ("papaya","ripe papaya",[
            "ripe papaya with yellow-orange skin, oval shape, full body",
            "papaya cut in half showing orange flesh and black seeds inside",
            "ripe papaya from side, full body"]),
        ("pomegranate","red pomegranate",[
            "round red pomegranate with crown, deep red skin, full body",
            "pomegranate cut in half showing bright red arils inside",
            "pomegranate from above showing crown and skin texture"]),
        ("coconut","whole brown coconut",[
            "whole brown coconut with fibrous husk, round shape",
            "halved coconut showing white flesh inside",
            "brown coconut from side showing fibrous texture"]),
        ("tender_coconut","green tender coconut",[
            "young green tender coconut, smooth skin, oval shape",
            "tender coconut with top cut showing inside",
            "green coconut from side, full body"]),
        ("guava","green guava",[
            "round-oval green guava with smooth skin",
            "guava cut in half showing pink-white flesh inside",
            "green guava with leaf attached, fresh"]),
        ("strawberry","red strawberry",[
            "heart-shaped red strawberry with seeds on surface",
            "strawberry with green leaves on top, bright red",
            "strawberry closeup showing seed texture and color"]),
        ("kiwi_whole","kiwi fruit",[
            "oval kiwi fruit with brown fuzzy skin",
            "kiwi sliced in half showing green flesh and black seeds",
            "kiwi from above showing oval brown fuzzy shape"]),
        ("lemon","fresh yellow lemon",[
            "oval bright yellow lemon with smooth skin",
            "lemon cut in half showing juicy segments inside",
            "lemon with green leaf attached, fresh"]),
        ("lime","fresh green lime",[
            "small round green lime with smooth bright skin",
            "lime cut in half showing juicy green flesh",
            "lime from above showing round shape"]),
        ("jackfruit","ripe jackfruit",[
            "large green spiky jackfruit exterior, full body",
            "jackfruit cut open showing yellow flesh pods inside",
            "single yellow jackfruit pod, ripe and sweet"]),
        ("dragon_fruit","pink dragon fruit",[
            "pink dragon fruit with green-tipped scales",
            "dragon fruit cut in half showing white flesh with black seeds",
            "dragon fruit from above showing scale pattern"]),
        ("lychee","fresh lychee",[
            "round lychee with pink-red rough textured shell",
            "lychee peeled showing translucent white flesh",
            "cluster of fresh lychees still on stem"]),
    ]
    for sub,name,descs in std:
        items += expand_standard("fruits", sub, descs, VIEWS_STD, fr_suf)
    for v in VIEWS_3:
        items.append(_item("fruits","fruit_group_tropical",
            f"A group of 8 assorted tropical fruits including mango, pineapple, papaya, banana and coconut, "
            f"naturally arranged in a colorful display, {v}, {fr_suf}"))
        items.append(_item("fruits","fruit_group_mixed",
            f"A group of 6 common fruits including red apple, orange, banana, green grapes, mango and strawberry, "
            f"arranged in a pile, {v}, {fr_suf}"))
        items.append(_item("fruits","fruit_basket",
            f"A wicker basket overflowing with assorted fresh fruits including mango, apple, orange, banana and pineapple, "
            f"{v}, {fr_suf}"))
    return dedup(items)

# ══════════════════════════════════════════════════
# 6. VEGETABLES
# ══════════════════════════════════════════════════
def vegetables():
    items = []
    vs = (f"{_BG}, professional studio product photography, Canon EOS R5, "
          "8k ultra realistic, accurate vegetable shape, true-to-life color, sharp detail, centered composition")
    veg = {
        "tomato":("red tomato",["ripe round red tomato with smooth shiny skin","red tomato from above showing green calyx","red tomato cut in half showing juicy interior"]),
        "onion":("brown onion",["round brown onion with papery skin and root end","brown onion cut in half showing white layered interior","whole brown onion from above"]),
        "onion_red":("red onion",["round red-purple onion with papery skin","red onion cut in half showing purple-white layers","red onion from above"]),
        "potato":("brown potato",["oval brown potato with earthy skin","potato cut in half showing white starchy interior","brown potato from above showing rough skin"]),
        "brinjal":("purple brinjal eggplant",["elongated purple brinjal with shiny smooth skin","purple brinjal from side, natural color","brinjal from above showing oval cross-section"]),
        "okra":("fresh green okra bhindi",["finger-shaped green okra with ridged skin","green okra from side showing tapered tip","okra cut in half showing seeds inside"]),
        "carrot":("orange carrot",["long tapering orange carrot with leafy green top","carrot from side showing smooth orange skin","carrot cut in half showing orange interior"]),
        "green_chili":("fresh green chili pepper",["slender bright green chili with pointed tip and stem","green chili from side showing curved shape","green chili closeup showing shiny surface"]),
        "capsicum_red":("red capsicum bell pepper",["round glossy red capsicum with thick walls","red capsicum from side showing lobed shape","red capsicum cut in half showing hollow interior"]),
        "capsicum_green":("green capsicum",["round glossy green capsicum bell pepper","green capsicum from side","green capsicum from above"]),
        "capsicum_yellow":("yellow capsicum",["round glossy yellow capsicum bell pepper","yellow capsicum from side","yellow capsicum from above"]),
        "cucumber":("fresh green cucumber",["long cylindrical dark green cucumber with smooth skin","cucumber from side showing full length","cucumber cut in half showing white flesh and seeds"]),
        "bitter_gourd":("bitter gourd karela",["elongated green bitter gourd with rough warty skin","karela from side showing full length","bitter gourd closeup showing warty texture"]),
        "cabbage":("green cabbage",["round green cabbage with tightly packed layered leaves","cabbage from above showing leaf pattern","cabbage cut in half showing white-green interior"]),
        "cauliflower":("white cauliflower",["white cauliflower with compact curd and green leaves","cauliflower from side showing white curd","cauliflower from above showing surface texture"]),
        "spinach":("fresh green spinach bunch",["bunch of dark green spinach leaves, fresh","spinach leaves spread flat, dark green","fresh spinach bunch tied together"]),
        "coriander":("fresh coriander leaves",["fresh green coriander herb bunch with roots","coriander leaves spread flat, bright green","coriander closeup showing delicate leaves"]),
        "ginger":("fresh ginger root",["knobbly tan-brown ginger root with bumpy surface","ginger root from side showing irregular shape","ginger root sliced showing yellow interior"]),
        "garlic":("white garlic bulb",["round garlic bulb with papery white skin","garlic bulb from side","garlic bulb broken apart showing individual cloves"]),
        "corn":("yellow corn on the cob",["yellow corn on the cob with green husk pulled back","corn cob from side showing yellow kernels","corn cob from above showing kernel rows"]),
        "drumstick":("drumstick moringa pods",["long thin green drumstick moringa pods, two or three together","drumstick pods from side showing full length","fresh drumstick with green skin"]),
        "bottle_gourd":("bottle gourd lauki",["long pale green bottle gourd with smooth skin","bottle gourd from side showing full length","bottle gourd from above"]),
    }
    for sub,(name,descs) in veg.items():
        items += expand_standard("vegetables", sub, descs, VIEWS_STD, vs)
    for v in VIEWS_3:
        items.append(_item("vegetables","veg_group_mixed",
            f"A group of 8 assorted fresh vegetables including tomato, onion, carrot, capsicum, potato and brinjal, "
            f"naturally arranged in a colorful display, {v}, {vs}"))
        items.append(_item("vegetables","veg_group_green",
            f"A group of 8 assorted green vegetables including cucumber, okra, capsicum, spinach and bitter gourd, "
            f"fresh display, {v}, {vs}"))
        items.append(_item("vegetables","veg_basket",
            f"A basket overflowing with assorted fresh Indian vegetables, colorful, fresh harvest quality, {v}, {vs}"))
        items.append(_item("vegetables","veg_flat_lay",
            f"A flat lay arrangement of assorted fresh vegetables including onion, tomato, chili, coriander and garlic, {v}, {vs}"))
    return dedup(items)

# ══════════════════════════════════════════════════
# 7. COOL DRINKS
# ══════════════════════════════════════════════════
def cool_drinks():
    items = []
    ds = (f"{_BG}, professional studio drink photography, Canon EOS R5, "
          "8k ultra realistic, condensation droplets, liquid transparency, sharp detail, centered composition")
    # Mojito hero
    moj_d = ["Classic Mojito in a tall glass with crushed ice, fresh mint leaves, lime slices and white rum, condensation on glass",
             "Virgin Mojito mocktail in tall clear glass with crushed ice, green mint leaves, lime wedges, soda bubbles",
             "Strawberry Mojito in a tall glass with crushed ice, red strawberries, mint and lime",
             "Mango Mojito in a tall glass with crushed ice, orange mango pieces and mint leaves",
             "Blue Mojito with blue curacao, crushed ice and lime in a tall glass",
             "Watermelon Mojito with pink watermelon, mint and lime in a glass"]
    moj_c = ["Classic Mojito with mint sprig and lime wheel on rim, full glass",
             "Virgin Mojito in a mason jar with metal straw",
             "Mojito from above showing crushed ice, mint and lime"]
    items += expand_hero("cool_drinks","mojito", moj_d, moj_c,
        ["front view","45 degree angle view","top view overhead","low angle hero shot","close-up detail view"], ds)
    drinks = {
        "lemonade":["fresh lemonade in a tall glass with ice cubes, lemon slices and mint","yellow lemonade in a mason jar with lemon wheel on rim","lemonade from above showing lemon and ice"],
        "cold_coffee":["iced cold coffee in a tall glass with cream layer on top","cold coffee with ice cubes and coffee foam","iced coffee from above showing cream and coffee layers"],
        "mango_lassi":["thick orange mango lassi in a tall glass with mango pieces on top","mango lassi in a clay kulhad glass","mango lassi from above showing thick creamy texture"],
        "sugarcane_juice":["fresh green sugarcane juice in a glass with lemon and ginger","sugarcane juice in a clay glass with crushed ice","sugarcane juice from above in a tall glass"],
        "coconut_water":["fresh tender coconut water in a glass with straw and ice cubes","coconut water in a round glass, clear and refreshing","coconut water with coconut pieces floating"],
        "orange_juice":["freshly squeezed orange juice in a glass with orange slice on rim","orange juice in a tall glass with ice and orange","orange juice from above showing bright color"],
        "watermelon_juice":["bright pink watermelon juice in a clear glass with mint","watermelon juice with ice cubes in a tall glass","watermelon juice from above showing pink color"],
        "nimbu_pani":["fresh nimbu pani in a steel glass with lemon and black salt","nimbu pani with ice cubes and mint leaves","nimbu pani from above in a round glass"],
        "rose_sharbat":["pink rose milk sharbat in a tall glass with rose petals","rose sharbat with basil seeds in a tall glass","rose sharbat from above showing pink color"],
        "buttermilk":["white spiced buttermilk chaas in a tall glass with curry leaves","chaas with cumin and chili garnish in a steel glass","buttermilk from above in a round glass"],
        "cola":["dark cola in a glass with ice cubes and bubbles","cola in a round glass with ice and lemon","cola from above showing dark color and bubbles"],
        "milkshake_vanilla":["thick white vanilla milkshake in a tall glass with whipped cream","vanilla milkshake with cherry on top","milkshake from above showing cream topping"],
        "milkshake_choco":["thick dark chocolate milkshake in a tall glass with whipped cream","chocolate milkshake with chocolate drizzle on cream","chocolate milkshake from above"],
        "iced_tea":["golden iced tea in a glass with lemon slice and ice cubes","iced tea with mint and lemon in a tall glass","iced tea from above showing amber color"],
    }
    for sub, descs in drinks.items():
        items += expand_standard("cool_drinks", sub, descs, VIEWS_3, ds)
    return dedup(items)

# ══════════════════════════════════════════════════
# 8. ANIMALS
# ══════════════════════════════════════════════════
def animals():
    items = []
    animal_list = {
        "cow":("Indian desi cow",["white and brown cow, full body, correct bovine anatomy","Indian desi cow standing calm, full body","cow with horns, full body side view"]),
        "buffalo":("Indian water buffalo",["dark grey buffalo with large curved horns, full body","water buffalo standing, muscular body, full body","buffalo from side, full body"]),
        "goat":("Indian goat",["white and brown goat with small horns, full body","Indian goat standing, full body","goat with beard and horns, full body"]),
        "sheep":("white woolly sheep",["fluffy white sheep with thick wool coat, full body","sheep grazing pose, white fluffy wool, full body","sheep from side, full body"]),
        "horse":("brown horse",["muscular brown horse with flowing mane, full body","brown horse standing tall, full body","horse from side showing full body"]),
        "elephant":("Indian elephant",["large grey elephant with curved tusks, full body","elephant with trunk down, full body","elephant from side showing full body"]),
        "tiger":("Bengal tiger",["orange tiger with black stripes, full body, correct anatomy","tiger standing alert, orange and black, full body","tiger from side, correct tiger species anatomy"]),
        "lion":("African lion",["golden-maned lion, muscular body, full body","lion standing proud, mane visible, full body","lion from side, full body"]),
        "dog_labrador":("golden Labrador dog",["friendly golden Labrador, golden fur, full body","Labrador sitting, tail wagging, full body","Labrador from side, golden coat"]),
        "dog_german":("German Shepherd dog",["tan and black German Shepherd, alert ears, full body","German Shepherd sitting, attentive pose, full body","German Shepherd from side, full body"]),
        "cat_persian":("white Persian cat",["fluffy white Persian cat, blue eyes, sitting","Persian cat full body, white fluffy fur","Persian cat from side, sitting"]),
        "rabbit":("white rabbit",["white rabbit with long ears, fluffy, sitting","white rabbit full body, upright","rabbit from side, sitting"]),
        "deer":("spotted deer Chital",["brown deer with white spots, antlers, full body","spotted deer standing, elegant, full body","Chital deer from side, full body"]),
        "camel":("Indian camel",["beige-brown camel, single hump, full body","camel standing, tall, full body","camel from side, full body"]),
        "peacock":("Indian peacock",["iridescent blue-green peacock with tail spread, full body","peacock with tail feathers fanned out, full body","peacock from side, full body"]),
        "monkey":("Indian rhesus monkey",["brown-grey monkey with pink face, sitting","monkey full body, alert expression","monkey from side, sitting"]),
    }
    for sub,(name,descs) in animal_list.items():
        items += expand_standard("animals", sub, descs,
            ["front view","side profile view","45 degree angle view"], ANIMAL_BASE)
    return dedup(items)

# ══════════════════════════════════════════════════
# 9. BIRDS & INSECTS
# ══════════════════════════════════════════════════
def birds_insects():
    items = []
    bird_list = {
        "peacock_b":("Indian peacock",["iridescent blue-green peacock, full body, tail fanned","peacock from side, tail spread","peacock walking"]),
        "parrot":("green Indian parrot",["bright green parrot with red beak, full body","green parrot perched, full body","parrot from side, full body"]),
        "hen_b":("Indian country hen",["brown hen with black feathers and red comb, full body","country hen standing, full body","hen from side, full body"]),
        "sparrow":("Indian house sparrow",["small brown-grey sparrow, full body","sparrow perched, full body","sparrow from side, full body"]),
        "crow":("Indian crow",["all-black glossy crow, full body","crow perched, full body","crow from side, full body"]),
        "eagle":("Indian eagle",["brown-golden eagle with spread wings, perched","eagle from side, perched","eagle full body, majestic pose"]),
        "pigeon":("grey pigeon",["grey pigeon with iridescent neck, full body","pigeon standing, full body","pigeon from side, full body"]),
        "flamingo":("pink flamingo",["long-legged pink flamingo, curved neck, full body","flamingo standing, pink plumage, full body","flamingo from side, full body"]),
        "owl":("barn owl",["white heart-faced barn owl, perched, full body","owl from side, wings folded","owl from front, round face"]),
        "kingfisher":("common kingfisher",["bright blue and orange kingfisher, perched, full body","kingfisher from side, colorful plumage","kingfisher full body, alert"]),
        "butterfly_monarch":("orange monarch butterfly",["spread wings showing orange and black pattern","monarch from above, wings spread","butterfly from side, wings folded"]),
        "butterfly_blue":("blue morpho butterfly",["spread wings showing iridescent blue","blue butterfly from above, wings spread","butterfly closeup showing wing pattern"]),
        "honeybee":("honey bee",["fuzzy yellow-black honey bee, wings visible, full body","bee from side, full body","bee from above, full body"]),
        "ladybug":("red ladybug",["round red ladybug with black spots, full body","ladybug from above, full body","ladybug from side, full body"]),
    }
    for sub,(name,descs) in bird_list.items():
        items += expand_standard("birds_insects", sub, descs,
            ["front view","side profile view","45 degree angle view"], ANIMAL_BASE)
    return dedup(items)

# ══════════════════════════════════════════════════
# 10. INDIAN SWEETS
# ══════════════════════════════════════════════════
def indian_sweets():
    items = []
    sw = (f"{_BG}, professional studio food photography, Canon EOS R5, "
          "8k ultra realistic, accurate Indian sweet shape, appetizing, sharp detail, centered composition")
    sweets = {
        "gulab_jamun":("gulab jamun",["round dark brown gulab jamun in golden sugar syrup in a silver bowl","two gulab jamun in syrup on a white plate","gulab jamun from above in a bowl"]),
        "rasgulla":("rasgulla",["soft white rasgulla sponge balls in clear sugar syrup in a glass bowl","rasgulla from above in a bowl","two rasgulla in syrup on a white plate"]),
        "kaju_katli":("kaju katli",["diamond-shaped white kaju katli with silver vark, arranged in rows on a plate","single kaju katli diamond piece closeup","kaju katli from above showing diamond arrangement"]),
        "ladoo_besan":("besan ladoo",["round yellow besan ladoo with ghee and cashews","besan ladoo from above showing round shape","besan ladoo closeup showing crumbly texture"]),
        "ladoo_motichur":("motichur ladoo",["round orange motichur ladoo with tiny fried boondi","motichur ladoo from above, orange color","motichur ladoo closeup showing boondi texture"]),
        "jalebi":("jalebi",["spiral orange crispy jalebi soaked in sugar syrup on a plate","jalebi from above showing spiral pattern","jalebi closeup showing syrup glaze"]),
        "mysore_pak":("Mysore pak",["square golden yellow Mysore pak with ghee texture","Mysore pak from above showing square shape","Mysore pak closeup showing crumbly texture"]),
        "barfi_milk":("milk barfi",["square white milk barfi with silver vark and pistachio garnish","barfi from above showing square shape","barfi closeup showing smooth texture"]),
        "halwa_sooji":("sooji halwa",["golden glossy sooji halwa with saffron and almonds in a bowl","halwa from above in a steel bowl","halwa closeup showing glossy texture"]),
        "kheer":("rice kheer",["creamy white rice kheer with cardamom and saffron in a silver bowl","kheer from above showing creamy texture","kheer with rose petals garnish in a bowl"]),
        "payasam":("semiya payasam",["creamy semiya vermicelli payasam with cashews, raisins and saffron in a steel bowl","payasam from above in a wide bowl","payasam closeup showing vermicelli texture"]),
        "peda":("peda",["round flat brown peda sweet with pistachio in center","peda from above showing round shape","peda closeup showing surface texture"]),
        "coconut_barfi":("coconut barfi",["white coconut barfi square with grated coconut texture","coconut barfi from above","coconut barfi closeup showing texture"]),
        "chikki":("peanut chikki",["brown peanut chikki brittle square with visible whole peanuts","chikki from above showing peanut pattern","chikki closeup showing caramel and peanut texture"]),
    }
    for sub,(name,descs) in sweets.items():
        items += expand_standard("indian_sweets", sub, descs,
            ["front view","45 degree angle view","top view overhead"], sw)
    for v in ["front view","top view overhead"]:
        items.append(_item("indian_sweets","sweets_assorted",
            f"A group of 8 assorted Indian sweets including ladoo, barfi, gulab jamun and jalebi, "
            f"arranged on a silver plate, festive display, {v}, {sw}"))
    return dedup(items)

# ══════════════════════════════════════════════════
# 11. FRAMES & BORDERS
# ══════════════════════════════════════════════════
def frames_borders():
    items = []
    fs = (f"{_BG}, professional studio photography, Canon EOS R5, "
          "8k ultra high definition, sharp crisp edges, detailed border texture, centered composition")
    designs = [
        ("frame_rose_red","rectangular photo frame decorated with red roses on all four sides, transparent center, elegant floral border"),
        ("frame_rose_yellow","rectangular frame with yellow rose flowers forming a complete floral border, transparent center"),
        ("frame_marigold","rectangular frame with orange marigold flowers and green leaves border, transparent center"),
        ("frame_lotus","rectangular frame with pink lotus flowers forming a decorative border, transparent center"),
        ("frame_jasmine","rectangular frame made of white jasmine flowers and green leaves border, transparent center"),
        ("frame_mixed_flower","rectangular frame with colorful mixed flowers including roses, lilies and marigolds, transparent center"),
        ("frame_kolam","rectangular frame with traditional South Indian white kolam geometric pattern"),
        ("frame_rangoli","rectangular border with colorful rangoli pattern and geometric floral motifs"),
        ("frame_paisley","rectangular frame with intricate gold paisley and vine pattern"),
        ("frame_temple","rectangular frame inspired by South Indian temple architecture with carved pillar design"),
        ("frame_mandala","rectangular border featuring mandala geometric pattern in gold and red"),
        ("frame_wedding_gold","ornate gold rectangular wedding photo frame with intricate filigree pattern"),
        ("frame_wedding_floral","elegant rectangular wedding frame with white flowers and gold accents, transparent center"),
        ("frame_certificate","formal rectangular certificate border with ornate corner decorations in gold and blue"),
        ("frame_gold_simple","modern rectangular frame with clean geometric double gold line border"),
        ("frame_vine","rectangular page border with green vine and leaf pattern running along all sides"),
        ("frame_corner_floral","decorative page border with floral corner elements in each corner, transparent center"),
        ("frame_ornate_gold","ornate golden decorative page border with corner flourishes and fine detail"),
        ("frame_diwali","rectangular Diwali themed frame with diya lamp and flower decorations, gold and orange"),
        ("frame_watercolor","rectangular watercolor floral frame with soft pink and purple flowers"),
    ]
    frame_views = [
        "front view", "top view overhead", "45 degree angle view",
        "close-up macro corner detail view", "side profile view",
    ]
    frame_sizes = [
        "portrait orientation",
        "landscape orientation",
        "square format",
        "A4 size",
        "Instagram square post size",
    ]
    for sub, det in designs:
        for v, sz in product(frame_views[:2], frame_sizes):
            items.append(_item("frames_borders", sub,
                f"A single {det}, {sz}, {v}, {fs}"))
    return dedup(items)

# ══════════════════════════════════════════════════
# 12-35. REMAINING CATEGORIES
# ══════════════════════════════════════════════════
def food_world():
    items = []
    dishes = {
        "pizza":["Italian pizza with tomato sauce, mozzarella and basil on a wooden board","pizza slice on a white plate","pizza from above showing full toppings"],
        "burger":["classic beef burger with lettuce, tomato, sesame bun on a board","burger from side showing layers","burger from above"],
        "sushi":["assorted Japanese sushi pieces on a slate board with soy sauce","sushi rolls from above on a plate","sushi nigiri pieces arranged in a row"],
        "pasta":["creamy fettuccine pasta with white sauce and parsley in a bowl","pasta from above in a white bowl","pasta closeup showing sauce and noodles"],
        "ramen":["Japanese ramen bowl with noodles, pork, egg and bamboo shoots","ramen from above showing toppings","ramen from side showing broth level"],
        "tacos":["Mexican tacos with beef filling and salsa on a plate","tacos from above on a plate","taco from side showing filling"],
        "fried_rice":["Chinese fried rice with egg and vegetables in a wok","fried rice from above in a bowl","fried rice from side in a plate"],
        "dim_sum":["steamed dim sum dumplings in a bamboo steamer basket","dim sum from above in steamer","dim sum from side"],
        "shawarma":["Middle Eastern shawarma wrap with grilled meat and vegetables","shawarma from side showing filling","shawarma from above"],
        "kebab":["grilled seekh kebab skewers with onion rings on a plate","kebab from side on a skewer","kebab from above on a plate"],
        "steak":["grilled beef steak with grill marks and vegetables","steak from above on a white plate","steak from side showing char marks"],
        "fried_chicken":["crispy golden fried chicken pieces piled on a plate","fried chicken from side showing crust","fried chicken from above"],
        "pad_thai":["Thai pad thai noodles with shrimp and peanuts","pad thai from above in a plate","pad thai from side showing ingredients"],
        "spring_roll":["crispy golden spring rolls with dipping sauce","spring roll cut in half showing filling","spring rolls from above"],
        "hot_dog":["American hot dog in a bun with mustard and ketchup","hot dog from side","hot dog from above showing toppings"],
    }
    for sub,descs in dishes.items():
        items += expand_food("food_world", sub, descs, VIEWS_3, FOOD_BASE)
    return dedup(items)

def watches():
    items = []
    ws = (f"{_BG}, professional studio product photography, Canon EOS R5, "
          "8k ultra realistic, metallic surface detail, glass reflection, sharp focus, centered composition")
    watch_list = {
        "watch_analog_silver":("men's classic analog silver watch",["stainless steel case, white dial, leather strap, front view","silver watch from side","watch from above showing dial"]),
        "watch_analog_gold":("men's gold luxury analog watch",["gold case, Roman numeral dial, gold bracelet, front view","gold watch from side","gold watch from above"]),
        "watch_sport_black":("men's black sport digital watch",["black rubber strap, digital display, bold design, front view","sport watch from side","sport watch from above"]),
        "watch_smart_black":("men's black smartwatch",["square touch screen, rubber strap, modern design, front view","smartwatch from side","smartwatch from above showing screen"]),
        "watch_smart_silver":("silver smartwatch",["round silver display, metal strap, front view","silver smartwatch from side","silver smartwatch from above"]),
        "watch_womens_rose":("women's rose gold watch",["delicate rose gold case, white dial, slim strap, front view","women's watch from side","women's watch from above"]),
        "watch_womens_silver":("women's silver fashion watch",["silver case with crystal stones, slim dial, front view","women's silver watch from side","women's watch from above"]),
        "watch_pocket":("antique pocket watch",["round silver case with chain, Roman numerals, front view","pocket watch from side","pocket watch from above"]),
        "watch_wall_white":("round white wall clock",["clean white face, black numbers, minimalist, front view","wall clock from side","wall clock from above"]),
        "watch_table_gold":("gold table alarm clock",["round gold finish, bell on top, front view","table clock from side","table clock from above"]),
    }
    for sub,(name,descs) in watch_list.items():
        items += expand_standard("watches", sub, descs,
            ["front view","45 degree angle view","top view overhead"], ws)
    return dedup(items)

def jewellery():
    items = []
    js = (f"{_BG}, professional studio jewelry photography, Canon EOS R5 macro lens, "
          "8k ultra realistic, gold metal mirror finish, gem facet reflections, sharp detail, centered composition")
    pieces = {
        "necklace_gold_chain":("gold chain necklace",["22 karat gold chain, intricate design, flat on surface","gold necklace from above","gold necklace front view closeup"]),
        "necklace_temple_gold":("South Indian temple gold necklace",["traditional temple design, gold, displayed flat","temple necklace from above","temple necklace front view"]),
        "necklace_diamond":("diamond pendant necklace",["silver chain, solitaire diamond pendant, displayed flat","diamond pendant from above","diamond pendant closeup"]),
        "earrings_jhumka_gold":("gold jhumka earrings",["pair of gold jhumka bell-drop earrings, displayed on surface","jhumka earrings from above","jhumka front view"]),
        "earrings_diamond_stud":("diamond stud earrings",["pair of diamond studs, silver setting, front view","diamond studs from above","diamond studs closeup"]),
        "earrings_kundan":("kundan earrings",["Rajasthani kundan design earrings, gold and red stones","kundan earrings from above","kundan earrings front view"]),
        "bangles_gold_set":("gold bangles set",["6 round plain gold bangles in a stack","bangles from above showing circular shape","bangles from side"]),
        "bangles_glass":("colorful glass bangles",["12 multicolored glass bangles in a row","glass bangles from above","glass bangles front view"]),
        "ring_gold_plain":("plain gold ring",["round band 22 karat yellow gold, displayed upright","gold ring from above","gold ring front view"]),
        "ring_diamond":("diamond solitaire ring",["round brilliant diamond, silver setting, displayed upright","diamond ring from above","diamond ring front view"]),
        "anklet_silver":("silver payal anklet",["delicate silver chain with bell charms, displayed flat","silver anklet from above","anklet from side"]),
        "mangalsutra":("black bead mangalsutra",["traditional gold and black bead necklace, displayed flat","mangalsutra from above","mangalsutra front view"]),
        "maang_tikka":("gold maang tikka",["traditional Indian forehead jewelry, gold and red stones","maang tikka from above","maang tikka front view"]),
        "bracelet_gold":("gold charm bracelet",["delicate gold links with charms, displayed flat","gold bracelet from above","gold bracelet front view"]),
        "nath_nose_ring":("Indian gold nose ring nath",["traditional gold nath with chain, bridal style","nose ring from above","nose ring front view"]),
    }
    for sub,(name,descs) in pieces.items():
        items += expand_standard("jewellery", sub, descs,
            ["front view","top view overhead","45 degree angle view"], js)
    return dedup(items)

def mobile_accessories():
    items = []
    s = BASE
    accs = {
        "phone_case_black":("black TPU phone case",["matte black, camera cutout, flat view","case from side","case from above"]),
        "phone_case_clear":("clear transparent phone case",["crystal clear design, front view","clear case from side","clear case from above"]),
        "earbuds_white":("white wireless earbuds",["in charging case opened, front view","earbuds from above","single earbud closeup"]),
        "earbuds_black":("black wireless earbuds",["sleek black, in case, front view","earbuds from above","single earbud side view"]),
        "charger_type_c":("white USB Type-C fast charger",["compact 20W with cable, front view","charger from side","charger from above"]),
        "power_bank":("black power bank 20000mAh",["rectangular, digital display, front view","power bank from side","power bank from above"]),
        "selfie_stick":("black selfie stick with tripod",["extended, front view","folded from side","from above"]),
        "wireless_charger":("white wireless charging pad",["flat round Qi pad, front view","pad from side","pad from above"]),
        "pop_socket":("colorful phone pop socket",["circular grip, front view","pop socket from side","closeup from above"]),
        "screen_guard":("tempered glass screen protector",["thin transparent glass, front view","from side showing thickness","from above"]),
    }
    for sub,(name,descs) in accs.items():
        items += expand_standard("mobile_accessories", sub, descs,
            ["front view","45 degree angle view","top view overhead"], s)
    return dedup(items)

def computer_accessories():
    items = []
    s = BASE
    accs = {
        "keyboard_mechanical":("black mechanical keyboard",["full-size RGB backlit, front view","from side","from above"]),
        "keyboard_wireless":("white slim wireless keyboard",["compact thin, front view","from side","from above"]),
        "mouse_gaming":("black RGB gaming mouse",["ergonomic design, front view","from side","from above"]),
        "mouse_wireless":("silver wireless mouse",["compact minimal, front view","from side","from above"]),
        "mouse_pad_large":("large black desk mouse pad",["flat non-slip, front view","from side","from above"]),
        "laptop_black":("black laptop computer",["open lid 15-inch, front view","from side","from above"]),
        "laptop_silver":("silver slim laptop",["open lid ultra-thin, front view","from side","from above"]),
        "monitor_curved":("black curved gaming monitor",["27-inch thin bezels, front view","from side","from above"]),
        "headset_gaming":("black RGB gaming headset",["over-ear with mic, front view","from side","from above"]),
        "webcam":("black HD clip webcam",["wide angle lens, front view","from side","from above"]),
    }
    for sub,(name,descs) in accs.items():
        items += expand_standard("computer_accessories", sub, descs,
            ["front view","45 degree angle view","top view overhead"], s)
    return dedup(items)

def footwear():
    items = []
    s = (f"{_BG}, professional studio product photography, Canon EOS R5, "
         "8k ultra realistic, leather grain and stitching detail, sharp focus, centered composition")
    shoes = {
        "mens_oxford_black":("men's black leather Oxford shoes",["polished leather, lace-up, full pair, front view","pair from side","pair from above"]),
        "mens_casual_white":("men's white canvas sneakers",["clean pair lace-up, front view","sneakers from side","sneakers from above"]),
        "mens_sports_blue":("men's blue and black running shoes",["mesh upper, cushioned sole, front view","running shoes from side","shoes from above"]),
        "mens_sandals_brown":("men's brown leather sandals",["open toe, buckle strap, full pair, front view","sandals from side","sandals from above"]),
        "mens_formal_brown":("men's brown leather formal shoes",["smooth leather, cap toe, full pair, front view","shoes from side","shoes from above"]),
        "womens_heels_black":("women's black high heel stilettos",["pointed toe, full pair, front view","heels from side","heels from above"]),
        "womens_heels_red":("women's red high heel pumps",["classic red, elegant pair, front view","heels from side","heels from above"]),
        "womens_flats_nude":("women's nude ballet flat shoes",["round toe, full pair, front view","flats from side","flats from above"]),
        "womens_sneakers_pink":("women's pink canvas sneakers",["lace-up, full pair, front view","sneakers from side","sneakers from above"]),
        "kolhapuri":("traditional brown Kolhapuri chappal",["handcrafted ethnic leather, front view","from side","from above"]),
        "kids_school_blue":("children's blue school shoes",["velcro strap, full pair, front view","from side","from above"]),
        "boots_ankle_black":("black leather ankle boots",["zip side, low heel, full pair, front view","boots from side","boots from above"]),
    }
    for sub,(name,descs) in shoes.items():
        items += expand_standard("footwear", sub, descs,
            ["front view","side profile view","45 degree angle view"], s)
    return dedup(items)

def indian_dress():
    items = []
    s = (f"{_BG}, professional studio fashion photography, Canon EOS R5, "
         "8k ultra realistic, fabric weave and embroidery detail, sharp focus, centered composition")
    dresses = {
        "saree_silk_red":("red Kanchipuram silk saree",["gold border, neatly folded flat, front view","from above","draped on hanger"]),
        "saree_cotton_blue":("blue cotton saree",["white border, folded flat, front view","from above","on hanger"]),
        "salwar_kameez_blue":("blue salwar kameez set",["embroidered neckline, with dupatta, front view","from above","on hanger"]),
        "lehenga_red":("red bridal lehenga",["heavy embroidery gold work, skirt and blouse, front view","from above","on hanger"]),
        "kurti_orange":("orange cotton kurti",["short printed kurti casual, front view","from above","on hanger"]),
        "kurta_white_mens":("men's white cotton kurta",["plain collarless traditional, front view","from above","on hanger"]),
        "sherwani_ivory":("ivory white wedding sherwani",["gold embroidery, full length, front view","from above","on hanger"]),
        "dhoti_white":("white cotton dhoti",["traditional draping folded flat, front view","from above","folded"]),
        "dupatta_embroidered":("embroidered silk dupatta",["colorful gold border, spread flat, front view","from above","from side"]),
    }
    for sub,(name,descs) in dresses.items():
        items += expand_standard("indian_dress", sub, descs,
            ["front view","top view overhead","45 degree angle view"], s)
    return dedup(items)

def bakery_snacks():
    items = []
    s = FOOD_BASE
    baked = {
        "cake_chocolate":("whole round chocolate cake",["dark chocolate frosting layered, front view","from above","slice from side"]),
        "cake_birthday":("colorful birthday cake",["white frosting, sprinkles, candles, front view","from above","slice from side"]),
        "croissant":("golden butter croissant",["flaky layered crescent shape, front view","from side","from above"]),
        "donut_glazed":("pink glazed donut",["round with hole, pink glaze, sprinkles, front view","from above","from side"]),
        "muffin_chocolate":("chocolate muffin",["dark top with chocolate chips, front view","from above","from side"]),
        "cookie_choco":("chocolate chip cookie",["round golden brown, front view","from above","from side"]),
        "brownie":("chocolate brownie square",["fudgy dense, powdered sugar, front view","from above","from side"]),
        "bread_loaf":("brown bread loaf",["sliced whole wheat, front view","from above","slices from side"]),
        "murukku":("crispy murukku",["spiral shaped golden rice flour, front view","from above","from side"]),
        "pakoda_onion":("crispy onion pakoda",["golden fritter, front view","from above","from side"]),
        "chakli":("spiral chakli snack",["golden brown crispy wheel, front view","from above","from side"]),
    }
    for sub,(name,descs) in baked.items():
        items += expand_food("bakery_snacks", sub, descs, VIEWS_3, s)
    return dedup(items)

def dairy_products():
    items = []
    s = FOOD_BASE
    dairy = {
        "milk_glass":("glass of white milk",["full glass fresh white milk, front view","from side","from above"]),
        "butter_block":("yellow butter block",["square gold foil wrapped, front view","from side","from above"]),
        "ghee_jar":("glass jar of golden ghee",["clarified butter glass jar, front view","from side","from above"]),
        "paneer_block":("white paneer block",["fresh cottage cheese square, front view","from side","from above"]),
        "curd_clay_pot":("white curd in clay pot",["thick curd earthen matka, front view","from side","from above"]),
        "icecream_vanilla":("vanilla ice cream cone",["white vanilla scoop, waffle cone, front view","from side","from above"]),
        "icecream_chocolate":("chocolate ice cream cone",["dark chocolate scoop on cone, front view","from side","from above"]),
        "icecream_mango":("mango kulfi stick",["orange mango kulfi on a stick, front view","from side","from above"]),
        "cheese_slice":("yellow cheese slice",["processed cheese square, front view","from side","from above"]),
        "yogurt_cup":("white yogurt cup",["sealed plastic cup, front view","from side","from above"]),
    }
    for sub,(name,descs) in dairy.items():
        items += expand_food("dairy_products", sub, descs, VIEWS_3, s)
    return dedup(items)

def beverages():
    items = []
    s = (f"{_BG}, professional studio drink photography, Canon EOS R5, "
         "8k ultra realistic, steam or condensation visible, sharp detail, centered composition")
    drinks = {
        "masala_chai":("hot masala chai",["in clay kulhad, steam rising, front view","from side","from above"]),
        "filter_coffee":("South Indian filter coffee",["steel tumbler davara set, dark brown, front view","from side","from above"]),
        "black_coffee":("hot black coffee",["white ceramic mug, steam, front view","from side","from above"]),
        "green_tea":("hot green tea",["clear glass mug, light green, front view","from side","from above"]),
        "haldi_milk":("golden turmeric haldi milk",["steel glass, golden color, front view","from side","from above"]),
        "orange_juice_h":("fresh orange juice",["bright orange, ice, front view","from side","from above"]),
        "water_bottle":("clear water bottle",["sealed cap, transparent, front view","from side","from above"]),
    }
    for sub,(name,descs) in drinks.items():
        items += expand_standard("beverages", sub, descs,
            ["front view","45 degree angle view","top view overhead"], s)
    return dedup(items)

def eggs():
    items = []
    s = FOOD_BASE
    egg_items = {
        "egg_white":("single white chicken egg",["oval smooth white shell, front view","from side","from above"]),
        "egg_brown":("single brown chicken egg",["oval smooth brown shell, front view","from side","from above"]),
        "eggs_six":("six white chicken eggs",["arranged in two rows of three, front view","from above","from side"]),
        "egg_boiled":("hard boiled egg",["peeled, cut in half showing yellow yolk, front view","from above","from side"]),
        "egg_fried":("sunny side up fried egg",["round yellow yolk, white cooked, front view","from above","from side"]),
        "eggs_carton":("12 eggs in cardboard carton",["open carton showing white eggs, front view","from above","from side"]),
    }
    for sub,(name,descs) in egg_items.items():
        items += expand_food("eggs", sub, descs, VIEWS_3, s)
    return dedup(items)

def bags():
    items = []
    s = (f"{_BG}, professional studio product photography, Canon EOS R5, "
         "8k ultra realistic, leather grain visible, sharp detail, centered composition")
    bag_list = {
        "handbag_black":("women's black leather handbag",["structured, top handle, front view","from side","from above"]),
        "handbag_brown":("women's brown leather tote bag",["large open top, front view","from side","from above"]),
        "clutch_gold":("gold metallic evening clutch",["small elegant, front view","from side","from above"]),
        "backpack_black":("black travel backpack",["large multiple pockets, front view","from side","from above"]),
        "backpack_school":("blue school bag",["colorful print, shoulder straps, front view","from side","from above"]),
        "sling_bag_brown":("brown leather sling bag",["small crossbody, front view","from side","from above"]),
        "wallet_black":("men's black leather bifold wallet",["slim, card slots, front view","from side","from above"]),
        "trolley_suitcase":("black hard shell trolley suitcase",["wheels, handle, large, front view","from side","from above"]),
        "laptop_bag_grey":("grey laptop shoulder bag",["padded compartment, front view","from side","from above"]),
        "shopping_bag":("white paper shopping bag",["with handles, front view","from side","from above"]),
    }
    for sub,(name,descs) in bag_list.items():
        items += expand_standard("bags", sub, descs,
            ["front view","45 degree angle view","top view overhead"], s)
    return dedup(items)

def clothing():
    items = []
    s = (f"{_BG}, professional studio fashion photography, Canon EOS R5, "
         "8k ultra realistic, fabric texture visible, sharp detail, centered composition")
    clothes = {
        "tshirt_white":("plain white cotton t-shirt",["round neck short sleeve flat lay, front view","from above","on hanger"]),
        "tshirt_black":("black cotton t-shirt",["round neck short sleeve flat lay, front view","from above","on hanger"]),
        "shirt_formal":("white formal dress shirt",["collared long sleeve buttoned, front view","from above","on hanger"]),
        "jeans_blue":("blue denim jeans",["straight fit, front view","from above folded","on hanger"]),
        "jacket_leather":("black leather biker jacket",["zip front, on hanger, front view","from side","from above"]),
        "hoodie_grey":("grey hoodie sweatshirt",["zip-up, flat lay, front view","from above","on hanger"]),
        "track_pants":("black sports track pants",["elastic waistband, flat lay, front view","from above","from side"]),
        "saree_blouse":("embroidered saree blouse",["sleeveless flat lay, front view","from above","from side"]),
    }
    for sub,(name,descs) in clothes.items():
        items += expand_standard("clothing", sub, descs,
            ["front view","top view overhead","45 degree angle view"], s)
    return dedup(items)

def cosmetics():
    items = []
    s = BASE
    beauty = {
        "lipstick_red":("red lipstick",["bullet shaped, cap off, front view","from side","from above"]),
        "lipstick_pink":("pink lipstick tube",["with cap, front view","from side","from above"]),
        "foundation":("liquid foundation bottle",["glass bottle, pump dispenser, front view","from side","from above"]),
        "mascara":("black mascara tube",["with wand, front view","from side","from above"]),
        "eyeshadow_palette":("colorful eyeshadow palette",["open quad palette, front view","from above","from side"]),
        "blush_compact":("pink blush powder compact",["round compact with brush, front view","from above","from side"]),
        "nail_polish_red":("red nail polish bottle",["glass bottle brush cap, front view","from side","from above"]),
        "face_wash_tube":("white face wash tube",["squeezable foam cleanser, front view","from side","from above"]),
        "moisturizer_jar":("moisturizer cream jar",["white glass jar, white lid, front view","from above","from side"]),
        "perfume_bottle":("glass perfume bottle",["elegant shaped, spray pump, golden cap, front view","from side","from above"]),
        "sunscreen_tube":("white sunscreen lotion tube",["SPF 50, squeezable, front view","from side","from above"]),
        "deodorant":("white roll-on deodorant",["oval bottle, front view","from side","from above"]),
    }
    for sub,(name,descs) in beauty.items():
        items += expand_standard("cosmetics", sub, descs,
            ["front view","45 degree angle view","top view overhead"], s)
    return dedup(items)

def electronics():
    items = []
    s = BASE
    gadgets = {
        "smartphone_black":("black Android smartphone",["front display on, thin design, front view","from side","from above"]),
        "smartphone_white":("white smartphone",["front display off, front view","from side","from above"]),
        "tablet_black":("black digital tablet",["10-inch display on, front view","from side","from above"]),
        "smartwatch":("black smartwatch",["square display, rubber strap, front view","from side","from above"]),
        "earphone_wired":("white in-ear earphones",["with cable coiled, front view","from side","from above"]),
        "bluetooth_speaker":("black Bluetooth speaker",["cylinder fabric grille, front view","from side","from above"]),
        "smart_tv":("black flat screen smart TV",["ultra thin, display on, front view","from side","from above"]),
        "camera_dslr":("black DSLR camera",["with lens, front view","from side","from above"]),
        "drone":("black quadcopter drone",["four rotors, front view","from side","from above"]),
        "projector":("white mini projector",["compact, lens forward, front view","from side","from above"]),
    }
    for sub,(name,descs) in gadgets.items():
        items += expand_standard("electronics", sub, descs,
            ["front view","45 degree angle view","top view overhead"], s)
    return dedup(items)

def furniture():
    items = []
    s = (f"{_BG}, professional studio interior photography, Canon EOS R5, "
         "8k ultra realistic, wood grain and fabric texture visible, sharp detail, centered composition")
    pieces = {
        "sofa_grey":("3-seater grey fabric sofa",["modern cushioned, front view","from side","from above"]),
        "sofa_leather":("brown leather 2-seater sofa",["wooden legs, classic, front view","from side","from above"]),
        "dining_table_set":("wooden 4-seater dining table with chairs",["front view","from side","from above"]),
        "bed_double":("double bed with white mattress",["wooden headboard, pillows, front view","from side","from above"]),
        "wardrobe_white":("white 3-door wardrobe",["mirror door, modern, front view","from side","from above"]),
        "study_desk_wood":("wooden study desk",["with drawer, front view","from side","from above"]),
        "office_chair_black":("black ergonomic office chair",["mesh back, armrests, front view","from side","from above"]),
        "bookshelf_wooden":("wooden 5-tier bookshelf",["with books, front view","from side","from above"]),
    }
    for sub,(name,descs) in pieces.items():
        items += expand_standard("furniture", sub, descs,
            ["front view","45 degree angle view","top view overhead"], s)
    return dedup(items)

def festivals():
    items = []
    s = (f"{_BG}, professional studio photography, Canon EOS R5, "
         "8k ultra realistic, vibrant colors, sharp detail, centered composition")
    fest = {
        "diya_clay":("clay diya oil lamp",["small round earthen lamp single wick, front view","from above","from side"]),
        "diya_lit":("lit glowing clay diya with flame",["warm golden light, front view","from above","from side"]),
        "diyas_group":("group of 5 lit clay diyas",["arranged in a row all burning, front view","from above","from side"]),
        "rangoli_colorful":("colorful floor rangoli pattern",["traditional Indian art, front view","from above","from side"]),
        "candle_lit":("lit candle with flame",["burning wax dripping, front view","from side","from above"]),
        "gift_box_red":("red wrapped gift box",["golden ribbon and bow, front view","from above","from side"]),
        "balloon_colorful":("colorful birthday balloons cluster",["6 mixed color balloons tied, front view","from above","from side"]),
        "holi_colors":("holi color powder pile",["bright pink and yellow powder, front view","from above","from side"]),
        "christmas_star":("golden Christmas star ornament",["metallic gold five-pointed, front view","from above","from side"]),
        "eid_crescent":("gold crescent moon and star",["Islamic symbol metallic gold, front view","from above","from side"]),
        "pongal_pot":("clay pot with sugarcane",["traditional Pongal pot, front view","from above","from side"]),
        "wedding_flowers":("red and yellow wedding flower decoration",["garland and arrangement, front view","from above","from side"]),
    }
    for sub,(name,descs) in fest.items():
        items += expand_standard("festivals", sub, descs,
            ["front view","45 degree angle view","top view overhead"], s)
    return dedup(items)

def dry_fruits_nuts():
    items = []
    s = FOOD_BASE
    nuts = {
        "almonds":("whole brown almonds",["pile of almonds in a bowl, front view","from above","from side"]),
        "cashews":("whole white cashew nuts",["pile in a bowl, front view","from above","from side"]),
        "walnuts":("brown walnuts",["whole and halved, front view","from above","from side"]),
        "pistachios":("green pistachios",["some shells open, front view","from above","from side"]),
        "raisins":("dark brown raisins",["pile in a bowl, front view","from above","from side"]),
        "dates":("brown Medjool dates",["soft oval dates in a bowl, front view","from above","from side"]),
        "peanuts":("roasted peanuts in shell",["pile on surface, front view","from above","from side"]),
        "mixed_nuts":("mixed dry fruits and nuts assortment",["colorful mix in a bowl, front view","from above","from side"]),
    }
    for sub,(name,descs) in nuts.items():
        items += expand_food("dry_fruits_nuts", sub, descs, VIEWS_3, s)
    return dedup(items)

def ayurvedic_herbal():
    items = []
    s = (f"{_BG}, professional studio product photography, Canon EOS R5, "
         "8k ultra realistic, accurate botanical details, natural color, sharp detail, centered composition")
    herbs = {
        "tulsi":("tulsi holy basil plant",["green leaves on stem in small pot, front view","from above","from side"]),
        "neem_leaves":("fresh neem leaves",["pinnate leaves on branch, front view","from above","from side"]),
        "turmeric":("raw turmeric root",["orange-yellow knobbly root, front view","from above","from side"]),
        "aloe_vera":("fresh aloe vera leaf",["thick succulent green, front view","from above","from side"]),
        "amla":("fresh amla Indian gooseberry",["small round pale yellow-green, front view","from above","from side"]),
        "cardamom":("green cardamom pods",["small oval green pods, front view","from above","from side"]),
        "cinnamon":("cinnamon sticks",["rolled bark sticks brown, front view","from above","from side"]),
        "saffron":("saffron strands",["fine orange-red threads, front view","from above","from side"]),
        "cloves":("whole cloves",["small dark brown buds, front view","from above","from side"]),
        "moringa":("moringa drumstick leaves",["small oval green leaves on stem, front view","from above","from side"]),
    }
    for sub,(name,descs) in herbs.items():
        items += expand_standard("ayurvedic_herbal", sub, descs,
            ["front view","top view overhead","45 degree angle view"], s)
    return dedup(items)

def cliparts():
    items = []
    s = BASE
    clipart_items = {
        "star_gold":("gold metallic five-pointed star",["glossy 3D look, front view","from above","from side"]),
        "heart_red":("red glossy heart shape",["smooth 3D red heart, front view","from above","from side"]),
        "crown_gold":("golden royal crown",["ornate with jewels, front view","from above","from side"]),
        "trophy_gold":("gold winner trophy cup",["classic with handles, front view","from side","from above"]),
        "ribbon_red":("red award ribbon with gold badge",["front view","from above","from side"]),
        "medal_gold":("gold medal with ribbon",["round medal, front view","from above","from side"]),
        "arrow_red":("bold red directional arrow pointing right",["front view","from above","from side"]),
        "flame_orange":("orange fire flame",["cartoon style, front view","from above","from side"]),
        "lightning_yellow":("yellow lightning bolt",["electric bolt shape, front view","from above","from side"]),
        "checkmark_green":("green checkmark tick",["bold green tick, front view","from above","from side"]),
    }
    for sub,(name,descs) in clipart_items.items():
        items += expand_standard("cliparts", sub, descs,
            ["front view","45 degree angle view","top view overhead"], s)
    return dedup(items)

def stationery():
    items = []
    s = BASE
    stat_items = {
        "pen_blue":("blue ballpoint pen",["click pen smooth barrel, front view","from side","from above"]),
        "pen_fountain":("black fountain pen",["nib visible, front view","from side","from above"]),
        "pencil_yellow":("yellow HB pencil",["sharpened tip, front view","from side","from above"]),
        "ruler":("transparent plastic 30cm ruler",["measurement markings, front view","from side","from above"]),
        "eraser_white":("white rectangular eraser",["smooth clean, front view","from side","from above"]),
        "scissors":("silver stainless steel scissors",["sharp blades red handles, front view","from side","from above"]),
        "notebook_spiral":("blue spiral notebook",["lined pages A5, front view","from side","from above"]),
        "calculator":("black scientific calculator",["button keys, front view","from side","from above"]),
        "highlighter":("yellow highlighter pen",["chisel tip, front view","from side","from above"]),
        "stapler":("black metal stapler",["heavy duty, front view","from side","from above"]),
    }
    for sub,(name,descs) in stat_items.items():
        items += expand_standard("stationery", sub, descs,
            ["front view","45 degree angle view","top view overhead"], s)
    return dedup(items)

def kitchen_vessels():
    items = []
    s = (f"{_BG}, professional studio product photography, Canon EOS R5, "
         "8k ultra realistic, metallic surface detail, sharp focus, centered composition")
    vessels = {
        "pressure_cooker":("silver aluminum pressure cooker",["weight valve, handles, front view","from side","from above"]),
        "kadai_iron":("black iron kadai wok",["round bottom two handles, front view","from side","from above"]),
        "tawa_flat":("flat iron tawa griddle pan",["round flat, front view","from side","from above"]),
        "steel_plate":("round stainless steel plate",["plain round, front view","from side","from above"]),
        "steel_bowl":("stainless steel bowl",["round deep, front view","from side","from above"]),
        "clay_pot":("brown clay cooking pot",["traditional with lid, front view","from side","from above"]),
        "brass_kalash":("shiny brass kalash vessel",["traditional pot with coconut, front view","from side","from above"]),
        "frying_pan":("non-stick frying pan",["black coating long handle, front view","from side","from above"]),
        "ladle_steel":("stainless steel cooking ladle",["long handle round bowl, front view","from side","from above"]),
        "water_pot_blue":("blue plastic water pot",["large with lid, front view","from side","from above"]),
    }
    for sub,(name,descs) in vessels.items():
        items += expand_standard("kitchen_vessels", sub, descs,
            ["front view","45 degree angle view","top view overhead"], s)
    return dedup(items)

def sports_equipment():
    items = []
    s = BASE
    sports = {
        "cricket_bat":("brown wooden cricket bat",["full size willow blade, front view","from side","from above"]),
        "cricket_ball":("red leather cricket ball",["round with seam, front view","from side","from above"]),
        "football":("black and white football",["round classic panels, front view","from side","from above"]),
        "badminton_set":("badminton racket and shuttlecock",["one racket one shuttlecock, front view","from side","from above"]),
        "tennis_racket":("tennis racket",["oval head, string, handle, front view","from side","from above"]),
        "basketball":("orange basketball",["round with black lines, front view","from side","from above"]),
        "dumbbells_pair":("pair of black dumbbells",["two 5kg dumbbells, front view","from side","from above"]),
        "yoga_mat":("purple rolled yoga mat",["thick foam rolled, front view","from side","from above"]),
        "cricket_helmet":("white cricket helmet with grille",["protective gear, front view","from side","from above"]),
        "chess_set":("classic chess board set",["black and white board with pieces, front view","from above","from side"]),
    }
    for sub,(name,descs) in sports.items():
        items += expand_standard("sports_equipment", sub, descs,
            ["front view","45 degree angle view","top view overhead"], s)
    return dedup(items)

def indian_foods_street():
    items = []
    s = FOOD_BASE
    dishes = {
        "chaat":["papdi chaat topped with yogurt, tamarind chutney and sev","chaat from above in a bowl","chaat from side"],
        "bhel_puri":["bhel puri with puffed rice, sev, tomatoes in a cone","bhel puri from above","bhel puri from side"],
        "vada_pav":["Mumbai vada pav with golden vada in white bun with chutney","vada pav from side","vada pav from above"],
        "puri_bhaji":["golden puri breads with yellow potato bhaji","puri bhaji from above","puri bhaji from side"],
        "dhokla":["steamed yellow dhokla squares garnished with green chili and curry leaves","dhokla from above","dhokla from side"],
        "kulfi_stick":["orange mango kulfi ice cream on a stick","kulfi from side","kulfi from above"],
        "lassi_kulhad":["sweet lassi in clay kulhad glass, creamy white","lassi from side","lassi from above"],
        "chai_kulhad":["hot masala chai in clay kulhad cup, steam rising","chai from side","chai from above"],
        "kachori":["crispy round kachori with flaky pastry","kachori from above","kachori from side"],
        "jalebi_fresh":["freshly fried orange jalebi, spiral, syrup glistening","jalebi from above","jalebi from side"],
    }
    for sub, descs in dishes.items():
        items += expand_food("indian_foods", sub, descs, VIEWS_3, s)
    return dedup(items)

# ══════════════════════════════════════════════════
# MASTER BUILD
# ══════════════════════════════════════════════════
def build_all():
    print("Building smart multi-variation prompt library...")
    print("20+ per item | 50+ for hero items | Fish capped at 70")
    print("=" * 60)
    registry = [
        ("food_indian",food_indian),
        ("poultry_chicken",poultry_chicken),
        ("fish_seafood",fish_seafood),
        ("flowers",flowers),
        ("fruits",fruits),
        ("vegetables",vegetables),
        ("cool_drinks",cool_drinks),
        ("animals",animals),
        ("birds_insects",birds_insects),
        ("indian_sweets",indian_sweets),
        ("frames_borders",frames_borders),
        ("food_world",food_world),
        ("watches",watches),
        ("jewellery",jewellery),
        ("mobile_accessories",mobile_accessories),
        ("computer_accessories",computer_accessories),
        ("footwear",footwear),
        ("indian_dress",indian_dress),
        ("bakery_snacks",bakery_snacks),
        ("dairy_products",dairy_products),
        ("beverages",beverages),
        ("eggs",eggs),
        ("bags",bags),
        ("clothing",clothing),
        ("cosmetics",cosmetics),
        ("electronics",electronics),
        ("furniture",furniture),
        ("festivals",festivals),
        ("dry_fruits_nuts",dry_fruits_nuts),
        ("ayurvedic_herbal",ayurvedic_herbal),
        ("cliparts",cliparts),
        ("stationery",stationery),
        ("kitchen_vessels",kitchen_vessels),
        ("sports_equipment",sports_equipment),
        ("indian_foods",indian_foods_street),
    ]
    out_dir = Path("prompts/splits")
    out_dir.mkdir(parents=True, exist_ok=True)
    from collections import defaultdict
    by_cat = defaultdict(list)
    grand_total = 0
    for cat_name, fn in registry:
        items = fn()
        grand_total += len(items)
        for item in items:
            by_cat[item["category"]].append(item)
        print(f"  ✅ {cat_name:<28} {len(items):>5} base → {len(items)*2:>5} images")
    all_items = []
    for items in by_cat.values():
        all_items.extend(items)
    random.shuffle(all_items)
    for i, item in enumerate(all_items):
        item["index"] = i
        item["filename"] = f"img_{i:06d}.png"
        item["status"] = "pending"
    file_names = []
    for cat, items in by_cat.items():
        fpath = out_dir / f"{cat}.json"
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, ensure_ascii=False)
        file_names.append(f"{cat}.json")
    index = {"total":len(all_items),"categories":list(by_cat.keys()),"files":file_names}
    with open(out_dir / "index.json", "w") as f:
        json.dump(index, f, indent=2)
    print("=" * 60)
    print(f"  GRAND TOTAL base : {grand_total}")
    print(f"  After ×2 pipeline: {grand_total * 2}")
    print(f"  Categories       : {len(by_cat)}")
    return all_items

if __name__ == "__main__":
    import statistics
    items = build_all()
    prompts = [i["prompt"] for i in items]
    wc = [len(p.split()) for p in prompts]
    dupes = len(prompts) - len(set(prompts))
    bad = [p for p in prompts if not p.startswith("A ")]
    no_bg = [p for p in prompts if "grey background" not in p.lower()]
    print("\n" + "="*60)
    print("  FINAL VERIFICATION")
    print("="*60)
    print(f"  Total base prompts : {len(items)}")
    print(f"  After ×2 pipeline  : {len(items)*2}")
    print(f"  Avg word count     : {statistics.mean(wc):.1f}")
    print(f"  Word range         : {min(wc)} - {max(wc)}")
    print(f"  Duplicates         : {dupes}")
    print(f"  Bad start          : {len(bad)}")
    print(f"  Missing grey BG    : {len(no_bg)}")
    status = "✅ ALL CLEAR!" if dupes==0 and len(bad)==0 and len(no_bg)==0 else "❌ ISSUES FOUND"
    print(f"  Status             : {status}")
    print("="*60)
    from collections import Counter
    subs = Counter(i["subcategory"] for i in items)
    print("\n  Top 20 subcategories (base × 2 = images):")
    for sub, cnt in subs.most_common(20):
        print(f"    {sub:<35} {cnt:>3} → {cnt*2:>4} images")
    print(f"\n🎯 DONE! {len(items)} base → {len(items)*2} unique images")

# ══════════════════════════════════════════════════
# MISSING CATEGORIES (from prompt_engine.py)
# ══════════════════════════════════════════════════

def spices():
    items = []
    s = (f"{_BG}, professional studio product photography, Canon EOS R5 macro lens, "
         "8k ultra realistic, accurate spice color and texture, sharp detail, centered composition")
    spice_list = {
        "turmeric_powder": ["turmeric powder in a small white bowl, bright yellow", "turmeric powder heaped on a spoon", "turmeric root and powder together"],
        "red_chili_powder": ["red chili powder in a white bowl, deep red", "red chili powder heaped, rich red color", "chili powder close-up texture"],
        "coriander_powder": ["coriander powder in a white bowl, earthy brown", "coriander seeds and powder together", "coriander powder close-up"],
        "cumin_seeds": ["cumin jeera seeds in a small bowl", "cumin seeds scattered on surface", "cumin seeds close-up detail"],
        "mustard_seeds": ["black mustard seeds in a small bowl", "mustard seeds scattered on surface", "mustard seeds close-up"],
        "black_pepper": ["whole black peppercorns in a bowl", "black pepper ground in a bowl", "peppercorns close-up on surface"],
        "cardamom": ["green cardamom pods in a bowl", "cardamom pods and seeds together", "cardamom close-up detail"],
        "cinnamon": ["cinnamon sticks bundle tied together", "cinnamon sticks and powder together", "cinnamon stick close-up"],
        "cloves": ["whole cloves in a small bowl", "cloves scattered on surface", "cloves close-up detail"],
        "star_anise": ["star anise whole pieces in a bowl", "star anise arranged on surface", "star anise close-up pattern"],
        "bay_leaves": ["dried bay leaves in a pile", "bay leaves on white surface", "bay leaves close-up texture"],
        "fenugreek": ["fenugreek methi seeds in a bowl", "fenugreek powder in a bowl", "fenugreek seeds close-up"],
        "saffron": ["saffron strands in a small bowl, orange-red", "saffron on white surface close-up", "saffron in a spoon"],
        "garam_masala": ["garam masala spice blend in a bowl", "garam masala powder mixed spice", "garam masala close-up texture"],
        "mixed_spices": ["assorted Indian spices in small bowls arranged flat lay", "five spice bowls arranged together", "colorful spices collection overhead"],
    }
    for sub, descs in spice_list.items():
        items += expand_standard("spices", sub, descs, VIEWS_STD[:3], s)
    return dedup(items)

def pooja_items():
    items = []
    s = (f"{_BG}, professional studio photography, Canon EOS R5, "
         "8k ultra realistic, vibrant colors, sharp detail, centered composition")
    pooja = {
        "diya_clay": ["single small clay diya lamp, round earthen, single wick", "clay diya top view showing wick hole", "diya with cotton wick inside"],
        "diya_lit": ["lit clay diya with golden flame burning, warm light", "lit diya flame close-up, warm glow", "burning diya from above, flame visible"],
        "agarbatti": ["agarbatti incense sticks bundle tied, white and fragrant", "burning agarbatti with white smoke", "agarbatti stick holder with sticks"],
        "camphor": ["white camphor tablets in a silver plate", "camphor block on plate", "camphor close-up white texture"],
        "kumkum": ["red kumkum powder in small silver bowl", "kumkum on white surface close-up", "kumkum in a traditional box"],
        "turmeric_haldi": ["yellow turmeric haldi powder in small bowl", "haldi on banana leaf", "turmeric powder close-up on surface"],
        "flowers_pooja": ["fresh marigold and jasmine flowers arranged for pooja", "rose petals scattered on banana leaf", "mixed pooja flowers arranged"],
        "coconut": ["whole coconut with tuft on top, pooja coconut", "coconut on banana leaf", "coconut with red marking for pooja"],
        "brass_lamp": ["shiny brass oil lamp diya, decorative", "brass diya with multiple wicks", "brass lamp from side close-up"],
        "silver_plate": ["clean round silver plate thali for pooja", "silver plate with items arranged", "silver thali from above empty"],
        "bell_brass": ["shiny brass pooja bell with handle", "brass bell from side", "brass bell close-up detail"],
        "sandalwood": ["sandalwood paste in small bowl", "sandalwood stick piece", "sandalwood powder on surface"],
        "banana_leaf": ["fresh green banana leaf flat lay", "banana leaf piece on surface", "banana leaf top view clean"],
        "pooja_set": ["complete pooja items arranged on a silver plate", "pooja thali with diya, flowers and kumkum", "traditional pooja setup flat lay"],
    }
    for sub, descs in pooja.items():
        items += expand_standard("pooja_items", sub, descs, VIEWS_STD[:3], s)
    return dedup(items)

def tools():
    items = []
    s = (f"{_BG}, professional studio product photography, Canon EOS R5, "
         "8k ultra realistic, metal surface detail, sharp focus, centered composition")
    tool_list = {
        "hammer": ["steel hammer with wooden handle, front view", "hammer from side", "hammer from above showing head"],
        "screwdriver_flat": ["flat head screwdriver with yellow handle", "screwdriver from side", "screwdriver tip close-up"],
        "screwdriver_phillips": ["Phillips cross head screwdriver with red handle", "screwdriver from side", "screwdriver from above"],
        "wrench_spanner": ["adjustable wrench spanner, silver steel", "spanner from side", "wrench from above"],
        "pliers": ["long nose pliers, steel handles", "pliers from side", "pliers open close-up"],
        "saw": ["hand saw with wooden handle, steel blade", "saw from side showing teeth", "saw from above"],
        "drill": ["electric power drill, black and yellow", "drill from side", "drill from above"],
        "measuring_tape": ["yellow measuring tape extended", "measuring tape coiled from above", "tape measure close-up numbers"],
        "level": ["spirit level tool, yellow", "level from side showing bubble", "level from above"],
        "chisel": ["flat chisel with wooden handle", "chisel from side", "chisel tip close-up"],
        "file_tool": ["metal file tool, flat bastard file", "file from side", "file surface close-up"],
        "scissors_large": ["large heavy duty scissors", "scissors from side", "scissors open front view"],
        "wire_cutter": ["wire cutter pliers", "wire cutter from side", "wire cutter tip close-up"],
        "toolbox": ["red metal toolbox open with tools inside", "toolbox from above showing contents", "closed toolbox from front"],
        "tool_set": ["set of 12 hand tools arranged flat lay", "5 tools arranged together", "screwdriver hammer pliers set"],
    }
    for sub, descs in tool_list.items():
        items += expand_standard("tools", sub, descs, VIEWS_STD[:3], s)
    return dedup(items)

def raw_meat():
    items = []
    s = (f"{_BG}, professional studio food photography, Canon EOS R5, "
         "8k ultra realistic, accurate meat color and texture, sharp detail, centered composition")
    meat = {
        "chicken_whole_raw": ["whole raw broiler chicken on white surface, pale skin", "raw whole chicken from above", "whole raw chicken from side"],
        "chicken_pieces": ["raw chicken pieces on white plate, bone-in cuts", "chicken cut pieces top view", "raw chicken drumstick close-up"],
        "chicken_breast": ["raw chicken breast fillet, pale pink", "chicken breast from above on plate", "chicken breast side view"],
        "mutton_pieces": ["fresh raw mutton pieces on white plate, red meat", "mutton cuts top view", "raw mutton close-up"],
        "mutton_leg": ["whole raw mutton leg on white surface", "mutton leg from side", "mutton leg from above"],
        "beef_slice": ["raw beef slices on white plate, red", "beef cuts top view", "raw beef close-up texture"],
        "pork_ribs": ["raw pork ribs on white plate", "pork ribs from above", "pork ribs from side"],
        "fish_fillet": ["raw fish fillet on white plate, pink flesh", "fish fillet from above", "fish fillet close-up texture"],
        "prawn_raw": ["raw fresh prawns on white plate, grey-pink", "raw prawns pile top view", "raw prawn close-up"],
        "keema_mince": ["raw minced meat keema on plate, red ground meat", "mince top view in bowl", "minced meat close-up"],
    }
    for sub, descs in meat.items():
        items += expand_food("raw_meat", sub, descs, VIEWS_3, s)
    return dedup(items)

def medical():
    items = []
    s = (f"{_BG}, professional studio product photography, Canon EOS R5, "
         "8k ultra realistic, clean clinical look, sharp detail, centered composition")
    med = {
        "tablets": ["white round tablets on white plate", "medicine tablets in strip blister pack", "tablets scattered close-up"],
        "capsules": ["colored capsules in a row on surface", "capsules in blister strip pack", "capsule close-up detail"],
        "syrup_bottle": ["glass syrup medicine bottle", "syrup bottle from side", "syrup bottle from above"],
        "injection": ["medical syringe with needle, clear body", "syringe from side", "syringe close-up tip"],
        "stethoscope": ["black stethoscope coiled on surface", "stethoscope from above flat lay", "stethoscope end piece close-up"],
        "thermometer": ["digital thermometer on white surface", "thermometer from side", "thermometer close-up display"],
        "blood_pressure": ["blood pressure monitor device", "BP monitor from above", "BP monitor from side"],
        "bandage": ["white bandage roll", "bandage unrolled on surface", "adhesive bandage strips arranged"],
        "first_aid_box": ["red first aid kit box closed", "first aid box open showing contents", "first aid box from above"],
        "mask": ["white surgical face mask", "mask from above", "mask from side"],
        "gloves": ["latex medical gloves blue pair", "gloves from above", "gloves from side"],
        "pill_organizer": ["weekly pill organizer box with compartments", "pill box from above showing days", "pill organizer close-up"],
    }
    for sub, descs in med.items():
        items += expand_standard("medical", sub, descs, VIEWS_STD[:3], s)
    return dedup(items)

def music():
    items = []
    s = (f"{_BG}, professional studio photography, Canon EOS R5, "
         "8k ultra realistic, sharp detail, centered composition")
    instruments = {
        "guitar_acoustic": ["acoustic guitar brown wooden body, front view", "acoustic guitar from side", "guitar from above flat lay"],
        "guitar_electric": ["electric guitar red body Stratocaster style, front view", "electric guitar from side", "guitar close-up headstock"],
        "tabla": ["pair of Indian tabla drums, front view", "tabla from above", "tabla from side"],
        "sitar": ["Indian sitar instrument, long neck, front view", "sitar from side", "sitar close-up frets"],
        "violin": ["violin with bow, front view", "violin from side", "violin from above"],
        "keyboard": ["digital piano keyboard front view", "keyboard from above", "keyboard from side"],
        "flute": ["wooden Indian flute bansuri, front view", "flute from side", "flute close-up"],
        "veena": ["Indian veena instrument, front view", "veena from side"],
        "mridangam": ["mridangam Indian drum, front view", "mridangam from side"],
        "harmonium": ["harmonium pump organ, front view", "harmonium from side", "harmonium from above"],
        "dholak": ["dholak barrel drum, front view", "dholak from side"],
        "drums_kit": ["drum kit on grey background, front view", "drum kit from side", "drum kit from above"],
        "microphone": ["professional microphone on stand, front view", "microphone close-up from side", "microphone from above"],
        "headphones_music": ["studio headphones over-ear, front view", "headphones from side", "headphones from above"],
        "speaker": ["portable Bluetooth speaker, front view", "speaker from side", "speaker from above"],
        "music_notes": ["colorful music notes arranged on surface", "musical notes flat lay", "music symbols arrangement"],
    }
    for sub, descs in instruments.items():
        items += expand_standard("music", sub, descs, VIEWS_STD[:3], s)
    return dedup(items)

def nature_trees():
    items = []
    s = (f"{_BG}, professional studio botanical photography, Canon EOS R5, "
         "8k ultra realistic, accurate botanical detail, natural color, sharp focus, centered composition")
    nature = {
        "banyan_tree": ["banyan tree with aerial roots, full body", "banyan tree from side", "banyan tree close-up roots"],
        "coconut_tree": ["tall coconut palm tree with coconuts, full body", "coconut tree from side", "coconut palm close-up fronds"],
        "mango_tree": ["mango tree with green fruits, full body", "mango tree from side", "mango tree branch with fruits"],
        "neem_tree": ["neem tree full body", "neem branch with leaves", "neem leaves close-up"],
        "peepal_tree": ["sacred peepal tree full body", "peepal tree from side", "peepal heart-shaped leaves close-up"],
        "bamboo": ["bamboo stalks cluster, green", "bamboo from side", "bamboo close-up texture"],
        "cactus": ["green cactus with spines, front view", "cactus from side", "cactus close-up spines"],
        "aloe_plant": ["aloe vera plant in pot, front view", "aloe plant from side", "aloe leaf close-up"],
        "tulsi_plant": ["tulsi holy basil plant in clay pot", "tulsi from side", "tulsi leaves close-up"],
        "rose_plant": ["rose bush with red flowers, front view", "rose plant from side", "rose plant close-up flower"],
        "lotus_plant": ["pink lotus flower on water leaf, front view", "lotus from above", "lotus close-up flower"],
        "sunflower_plant": ["sunflower on tall green stem, full plant", "sunflower plant from side", "sunflower from above"],
        "banana_plant": ["banana plant with large leaves, full body", "banana plant from side", "banana plant leaves close-up"],
        "papaya_plant": ["papaya tree with fruits hanging, full body", "papaya plant from side", "papaya plant close-up fruits"],
        "paddy_rice": ["paddy rice stalks with grain, full body", "paddy field stalks from side", "rice grains on stalk close-up"],
        "sugarcane": ["sugarcane stalks bundle, full body", "sugarcane from side", "sugarcane node close-up"],
        "wheat_crop": ["wheat crop stalks with grain heads", "wheat from side", "wheat grain head close-up"],
        "grass_green": ["fresh green grass patch, front view", "grass from above", "grass blade close-up"],
        "fern": ["green fern plant with fronds", "fern from side", "fern frond close-up"],
        "money_plant": ["money plant with heart-shaped leaves, in pot", "money plant from side", "money plant leaves close-up"],
    }
    for sub, descs in nature.items():
        items += expand_standard("nature_trees", sub, descs, VIEWS_STD[:3], s)
    return dedup(items)

def offer_logos():
    items = []
    s = (f"{_BG}, professional graphic design studio, Canon EOS R5, "
         "8k ultra high definition, vibrant colors, sharp crisp edges, centered composition")
    logos = {
        "offer_50_off": ["bold red 50% OFF sale badge, round shape, white text", "50% discount sticker red round", "50% off badge front view"],
        "offer_buy_one": ["Buy One Get One Free badge, green circular badge", "BOGO offer label green", "buy one get one badge"],
        "offer_new": ["NEW launch badge, blue star burst shape", "NEW arrival sticker badge", "new product launch label"],
        "offer_free": ["FREE offer badge, orange rounded rectangle", "free gift badge orange", "free offer sticker"],
        "offer_sale": ["SALE banner red rectangular badge with gold text", "sale tag red sticker", "sale badge front view"],
        "offer_discount": ["discount price tag, yellow with black text", "price off badge yellow", "discount label sticker"],
        "offer_best": ["BEST SELLER golden star badge", "best seller badge golden", "top seller label badge"],
        "offer_limited": ["LIMITED OFFER red circular badge with clock icon", "limited time offer badge", "limited deal sticker"],
        "offer_hot": ["HOT DEAL red fire badge with flame", "hot offer badge red", "hot deal label sticker"],
        "offer_flat": ["FLAT 30% OFF badge, bold typography", "flat discount badge", "percent off label"],
        "logo_star_gold": ["golden star logo badge, 5-pointed star", "gold star award badge", "star logo front view"],
        "logo_crown": ["gold royal crown logo, ornate design", "crown badge golden", "crown logo front view"],
        "logo_shield": ["blue shield logo with checkmark", "security shield badge", "shield logo front view"],
        "logo_circle_badge": ["professional circular logo badge template, gold border", "round company badge", "circle badge design"],
        "logo_ribbon": ["red award ribbon with gold center circle", "first place ribbon badge", "award ribbon front view"],
        "logo_starburst": ["yellow starburst promotional badge", "star burst offer badge", "starburst label design"],
        "logo_stamp": ["round rubber stamp effect badge, red ink", "official stamp badge", "stamp design front view"],
        "logo_tag": ["price tag shape with string hole", "hang tag badge design", "product tag label"],
        "logo_banner": ["promotional banner ribbon shape, red with gold text area", "ribbon banner design", "banner label shape"],
        "logo_seal": ["official gold wax seal badge", "quality seal stamp gold", "seal badge front view"],
    }
    for sub, descs in logos.items():
        items += expand_standard("offer_logos", sub, descs, VIEWS_STD[:3], s)
    return dedup(items)

def sky_celestial():
    items = []
    s = (f"{_BG}, professional studio photography, Canon EOS R5, "
         "8k ultra realistic, vibrant colors, sharp crisp detail, centered composition")
    sky = {
        "sun": ["bright yellow glowing sun with rays, full circle", "sun from front view", "sun close-up with corona rays"],
        "moon_full": ["full moon bright white circle", "full moon front view", "moon surface texture close-up"],
        "moon_crescent": ["gold crescent moon shape", "crescent moon side view", "crescent moon close-up"],
        "star_gold": ["single shining gold star five-pointed", "gold star from above", "star close-up shimmer"],
        "stars_cluster": ["cluster of twinkling stars arranged", "stars scattered arrangement", "stars close-up"],
        "cloud_white": ["white fluffy cloud shape", "cloud from front view", "cloud from below"],
        "rainbow": ["full rainbow arc colorful", "rainbow front view", "rainbow close-up colors"],
        "lightning_bolt": ["yellow lightning bolt electric", "lightning from front", "lightning close-up"],
        "snowflake": ["detailed crystalline snowflake", "snowflake from above", "snowflake close-up"],
        "comet": ["comet with glowing tail", "comet from front view", "comet tail close-up"],
        "planet_earth": ["planet Earth blue and green sphere", "Earth from front", "Earth from side"],
        "planet_saturn": ["Saturn with rings, gold planet", "Saturn from front", "Saturn from side"],
        "solar_system": ["solar system planets arranged", "planets in a row overhead", "planet collection"],
        "sunrise": ["orange sunrise glow effect", "sunrise light rays", "sunrise close-up horizon glow"],
        "night_sky": ["night sky with stars and moon", "starry night from above", "night sky close-up stars"],
    }
    for sub, descs in sky.items():
        items += expand_standard("sky_celestial", sub, descs, VIEWS_STD[:3], s)
    return dedup(items)

def pots_vessels():
    items = []
    s = (f"{_BG}, professional studio product photography, Canon EOS R5, "
         "8k ultra realistic, surface detail visible, sharp focus, centered composition")
    pots = {
        "clay_pot_round": ["round brown clay pot with lid, traditional", "clay pot from side", "clay pot from above"],
        "clay_pot_large": ["large brown clay matka pot", "clay matka from side", "clay matka from above"],
        "flower_pot_red": ["red terracotta flower pot with plant", "flower pot from side", "flower pot from above"],
        "copper_pot": ["shiny copper pot with lid, traditional", "copper pot from side", "copper pot from above"],
        "brass_pot": ["golden brass lota pot, traditional", "brass pot from side", "brass pot from above"],
        "steel_bucket": ["shiny stainless steel bucket with handle", "steel bucket from side", "steel bucket from above"],
        "plastic_bucket_blue": ["blue plastic bucket with handle", "bucket from side", "bucket from above"],
        "water_pot_clay": ["large clay water pot, traditional matka", "water pot from side", "water pot from above"],
        "uruli": ["wide Kerala brass uruli vessel", "uruli from side", "uruli from above"],
        "kendai": ["traditional South Indian brass kendai vessel", "kendai from side", "kendai from above"],
        "milk_vessel": ["steel milk vessel with handle", "milk vessel from side", "milk vessel from above"],
        "vessel_with_lid": ["steel vessel with lid, cooking pot", "vessel from side", "vessel from above"],
        "garden_pot": ["ceramic garden flower pot", "garden pot from side", "garden pot from above"],
        "watering_can": ["green plastic watering can", "watering can from side", "watering can from above"],
        "drum_barrel": ["blue plastic water storage drum", "drum from side", "drum from above"],
    }
    for sub, descs in pots.items():
        items += expand_standard("pots_vessels", sub, descs, VIEWS_STD[:3], s)
    return dedup(items)

def vehicles_full():
    items = []
    s = (f"{_BG}, professional studio automotive photography, Canon EOS R5, "
         "8k ultra realistic, clean polished bodywork, studio car photography, centered composition")
    # Cars
    cars = {
        "maruti_alto": ["Maruti Alto hatchback car, front view", "Maruti Alto side profile view", "Maruti Alto 3/4 front view"],
        "maruti_swift": ["Maruti Swift hatchback, front view", "Maruti Swift side profile", "Maruti Swift 3/4 view"],
        "hyundai_creta": ["Hyundai Creta SUV, front view", "Hyundai Creta side profile", "Hyundai Creta 3/4 view"],
        "tata_nexon": ["Tata Nexon SUV, front view", "Tata Nexon side profile", "Tata Nexon 3/4 view"],
        "honda_city": ["Honda City sedan, front view", "Honda City side profile", "Honda City 3/4 view"],
        "toyota_innova": ["Toyota Innova MPV, front view", "Toyota Innova side profile", "Toyota Innova 3/4 view"],
        "mahindra_scorpio": ["Mahindra Scorpio SUV, front view", "Mahindra Scorpio side profile", "Mahindra Scorpio 3/4 view"],
        "auto_rickshaw": ["Indian auto rickshaw three-wheeler, front view", "auto rickshaw side profile", "auto rickshaw 3/4 view"],
    }
    for sub, descs in cars.items():
        items += expand_standard("vehicles_cars", sub, descs, VIEWS_STD[:2], s)

    # Bikes
    bikes_s = (f"{_BG}, professional studio motorcycle photography, Canon EOS R5, "
               "8k ultra realistic, clean polished bodywork, studio motorcycle photography, centered composition")
    bikes = {
        "hero_splendor": ["Hero Splendor motorcycle, side profile", "Hero Splendor front view", "Hero Splendor 3/4 view"],
        "bajaj_pulsar": ["Bajaj Pulsar 150 motorcycle, side profile", "Bajaj Pulsar front view", "Bajaj Pulsar 3/4 view"],
        "royal_enfield_classic": ["Royal Enfield Classic 350, side profile", "Royal Enfield front view", "Royal Enfield 3/4 view"],
        "yamaha_r15": ["Yamaha R15 sports bike, side profile", "Yamaha R15 front view", "Yamaha R15 3/4 view"],
        "honda_activa": ["Honda Activa scooter, side profile", "Activa front view", "Activa 3/4 view"],
        "tvs_jupiter": ["TVS Jupiter scooter, side profile", "TVS Jupiter front view", "TVS Jupiter 3/4 view"],
        "cycle": ["bicycle front view", "bicycle side profile", "bicycle 3/4 view"],
    }
    for sub, descs in bikes.items():
        items += expand_standard("vehicles_bikes", sub, descs, VIEWS_STD[:2], bikes_s)

    return dedup(items)

def jewellery_models():
    items = []
    s = (f"{_BG}, professional studio fashion portrait photography, "
         "Canon EOS R5 85mm portrait lens, 8k ultra realistic, "
         "razor sharp focus, softbox studio lighting, centered composition")
    models = {
        "necklace_model": ["Indian woman wearing gold necklace, elegant studio portrait", "South Indian woman with temple gold necklace portrait", "woman in silk saree wearing layered gold necklace portrait"],
        "earrings_model": ["Indian woman wearing gold jhumka earrings, studio portrait", "woman gold chandbali earrings portrait", "woman with diamond earrings elegant portrait"],
        "bangles_model": ["Indian woman hands with gold bangles close-up", "woman bridal gold bangles wrist portrait", "woman with colorful glass bangles hands portrait"],
        "bridal_model": ["South Indian bride full bridal gold jewellery portrait", "Tamil bride temple jewellery portrait", "Indian bride gold necklace earring set portrait"],
        "ring_model": ["woman showing diamond ring close-up hands", "Indian woman gold ring on finger portrait", "woman hand with gold ring close-up"],
        "maang_tikka_model": ["Indian woman wearing maang tikka forehead jewellery portrait", "bride with maang tikka and nose ring portrait", "woman forehead tikka close-up portrait"],
    }
    for sub, descs in models.items():
        items += expand_standard("jewellery_models", sub, descs, ["front view", "three-quarter view", "close-up"], s)
    return dedup(items)

def office_models():
    items = []
    s = (f"{_BG}, professional studio fashion portrait photography, "
         "Canon EOS R5 85mm portrait lens, 8k ultra realistic, "
         "razor sharp focus, softbox studio lighting, centered composition")
    office = {
        "professional_woman": ["Indian professional woman in formal office blazer, confident portrait", "businesswoman in formal suit, studio portrait", "Indian corporate woman smart formal portrait"],
        "professional_man": ["Indian businessman in formal suit, confident studio portrait", "man in formal shirt and trousers, professional portrait", "Indian corporate man in blazer portrait"],
        "casual_woman": ["Indian woman in smart casual kurta and jeans, portrait", "young Indian woman modern casual dress portrait", "woman in western casual top, friendly portrait"],
        "casual_man": ["Indian man in casual shirt, friendly portrait", "young man smart casual portrait", "Indian boy casual modern portrait"],
        "doctor": ["Indian doctor in white coat, stethoscope, portrait", "female doctor professional portrait", "male doctor studio portrait"],
        "teacher": ["Indian woman teacher in formal dress, portrait", "male teacher formal portrait", "teacher with book studio portrait"],
    }
    for sub, descs in office.items():
        items += expand_standard("office_models", sub, descs, ["front view", "three-quarter view", "close-up head shot"], s)
    return dedup(items)

def sports():
    items = []
    s = (f"{_BG}, professional sports photography, Canon EOS R5, "
         "8k ultra realistic, action frozen detail, sharp focus, centered composition")
    sport = {
        "cricket_bat_action": ["cricket bat ready to bat stance, front view", "cricket bat swing action side view", "cricket bat grip close-up"],
        "cricket_bowl": ["cricket bowler action pose, side view", "bowler delivery stride", "bowling action front view"],
        "football_kick": ["football player kicking ball action", "footballer running with ball", "football kick close-up"],
        "badminton_smash": ["badminton player smash action, side view", "badminton serve action", "badminton player front view"],
        "kabaddi": ["kabaddi player action pose, front view", "kabaddi raid pose side view", "kabaddi player stance"],
        "boxing": ["boxer in fighting stance, front view", "boxer gloves raised side view", "boxing punch action"],
        "chess_game": ["chess game in progress top view", "chess pieces on board front view", "chess king piece close-up"],
        "running": ["sprinter running action, side view", "runner in full stride front view", "running shoes close-up action"],
        "yoga_pose": ["yoga tree pose front view", "yoga downward dog pose", "yoga meditation pose front view"],
        "swimming": ["swimmer action in water side view", "swimming stroke overhead view", "swimmer goggles close-up"],
    }
    for sub, descs in sport.items():
        items += expand_standard("sports", sub, descs, ["front view", "side profile view", "45 degree angle view"], s)
    return dedup(items)

# ══════════════════════════════════════════════════
# UPDATE build_all() to include new categories
# ══════════════════════════════════════════════════
def build_all_complete():
    """Complete build including all categories from both generators."""
    print("Building COMPLETE prompt library (ALL categories)...")
    print("=" * 60)
    registry = [
        # Original generate_prompts.py categories
        ("food_indian",          food_indian),
        ("poultry_chicken",      poultry_chicken),
        ("fish_seafood",         fish_seafood),
        ("flowers",              flowers),
        ("fruits",               fruits),
        ("vegetables",           vegetables),
        ("cool_drinks",          cool_drinks),
        ("animals",              animals),
        ("birds_insects",        birds_insects),
        ("indian_sweets",        indian_sweets),
        ("frames_borders",       frames_borders),
        ("food_world",           food_world),
        ("watches",              watches),
        ("jewellery",            jewellery),
        ("mobile_accessories",   mobile_accessories),
        ("computer_accessories", computer_accessories),
        ("footwear",             footwear),
        ("indian_dress",         indian_dress),
        ("bakery_snacks",        bakery_snacks),
        ("dairy_products",       dairy_products),
        ("beverages",            beverages),
        ("eggs",                 eggs),
        ("bags",                 bags),
        ("clothing",             clothing),
        ("cosmetics",            cosmetics),
        ("electronics",          electronics),
        ("furniture",            furniture),
        ("festivals",            festivals),
        ("dry_fruits_nuts",      dry_fruits_nuts),
        ("ayurvedic_herbal",     ayurvedic_herbal),
        ("cliparts",             cliparts),
        ("stationery",           stationery),
        ("kitchen_vessels",      kitchen_vessels),
        ("sports_equipment",     sports_equipment),
        ("indian_foods",         indian_foods_street),
        # NEW categories added in final version
        ("spices",               spices),
        ("pooja_items",          pooja_items),
        ("tools",                tools),
        ("raw_meat",             raw_meat),
        ("medical",              medical),
        ("music",                music),
        ("nature_trees",         nature_trees),
        ("offer_logos",          offer_logos),
        ("sky_celestial",        sky_celestial),
        ("pots_vessels",         pots_vessels),
        ("effects",              lambda: __import__('generate_prompts').build_effects()),
        ("sports",               sports),
        ("jewellery_models",     jewellery_models),
        ("office_models",        office_models),
    ]

    out_dir = Path("prompts/splits")
    out_dir.mkdir(parents=True, exist_ok=True)

    from collections import defaultdict
    grand_total = 0
    all_file_names = []

    for cat_name, fn in registry:
        try:
            items = fn()
        except Exception as e:
            print(f"  SKIP {cat_name}: {e}")
            continue

        grand_total += len(items)
        fpath = out_dir / f"{cat_name}.json"
        random.shuffle(items)
        for i, item in enumerate(items):
            item["index"]    = i
            item["filename"] = f"img_{i:06d}.png"
            item["status"]   = "pending"
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        all_file_names.append(f"{cat_name}.json")
        print(f"  OK  {cat_name:<30} {len(items):>5} base → ~{len(items)*2:>5} images")

    # Rebuild index
    index = {
        "total":      grand_total,
        "categories": [f.replace(".json","") for f in all_file_names],
        "files":      all_file_names,
    }
    with open(out_dir / "index.json", "w") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print("=" * 60)
    print(f"  TOTAL base prompts : {grand_total}")
    print(f"  Expected images    : ~{grand_total * 2}")
    print(f"  Categories         : {len(all_file_names)}")
    print("  DONE!")
    return grand_total


if __name__ == "__main__":
    build_all_complete()

def build_effects():
    """Effects prompts (called from build_all_complete)."""
    import json
    from pathlib import Path
    eff = Path("prompts/splits/effects.json")
    if eff.exists():
        return json.loads(eff.read_text("utf-8"))
    return []
