"""
╔══════════════════════════════════════════════════════════════╗
║  PNG Library — Unified Prompt Engine V2.0                   ║
║  (Merged from prompt_engine.py + generate_prompts.py)       ║
╠══════════════════════════════════════════════════════════════╣
║  KEY CHANGES V2.0:                                          ║
║  • MERGED: Two engines into one unified file                ║
║  • FLUX-STYLE: Natural sentence prompts (45-80 words)       ║
║  • REMOVED: Redundant BASE_SUFFIX, ANGLES, LIGHTING etc.    ║
║  • REMOVED: Old comma-keyword style (SD-style)              ║
║  • ADDED: expand_standard/expand_hero/expand_food helpers   ║
║  • KEPT: All category data (23 categories)                  ║
║  • KEPT: load_all_prompts() interface (unchanged)           ║
╠══════════════════════════════════════════════════════════════╣
║  FLUX.2 Klein Prompt Rules:                                 ║
║  1. Natural descriptive sentences — NOT keyword lists       ║
║  2. Subject + visual details + angle + lighting + BG        ║
║  3. 45-80 words — sweet spot for FLUX.2 Klein               ║
║  4. Light grey BG emphasized (model tends to go dark)       ║
║  5. NO negative prompts — FLUX ignores them                 ║
║  6. NO "8k, Canon EOS, photorealistic" — FLUX knows quality ║
╚══════════════════════════════════════════════════════════════╝
"""

import random
import json
from pathlib import Path
from itertools import product as iterproduct

random.seed(42)

# ══════════════════════════════════════════════════
# FLUX-STYLE BASE SUFFIXES (simplified, natural)
# FLUX.2 Klein responds better to natural language
# ══════════════════════════════════════════════════

_BG = (
    "isolated on a solid plain light grey background, "
    "not black, not white, clean light grey studio backdrop"
)

# General products
BASE = (
    f"{_BG}, soft even studio lighting, "
    "ultra sharp commercial product photography quality"
)

# Food items
FOOD_BASE = (
    f"{_BG}, professional studio food photography, "
    "appetizing true-to-life color and texture, soft studio lighting"
)

# Animals
ANIMAL_BASE = (
    f"{_BG}, professional studio animal photography, "
    "correct species anatomy, natural pose, soft studio lighting"
)

# Fashion models
MODEL_BASE = (
    f"{_BG}, professional studio fashion portrait photography, "
    "soft flattering studio lighting, natural skin tone"
)

# Vehicles
VEHICLE_BASE = (
    f"{_BG}, professional automotive photography, "
    "showroom quality, soft directional studio lighting"
)

# ══════════════════════════════════════════════════
# VIEW POOLS — used across categories
# ══════════════════════════════════════════════════
VIEWS_ALL = [
    "front view", "side profile view", "45 degree angle view",
    "top view overhead", "low angle hero shot", "close-up macro detail view",
]
VIEWS_FOOD = [
    "front view eye level", "45 degree angle view",
    "top view overhead flat lay", "low angle hero shot",
    "close-up macro detail view", "three-quarter angle view",
]
VIEWS_STD = [
    "front view", "side profile view", "45 degree angle view",
    "top view overhead", "close-up macro detail view",
]
VIEWS_3 = ["front view", "45 degree angle view", "top view overhead"]
VIEWS_FLOWER = [
    "front view", "45 degree angle view", "close-up macro view",
    "top view overhead", "side profile view",
]
VIEWS_ANIMAL = [
    "front view", "side profile view", "45 degree angle view",
    "close-up portrait view", "three-quarter view",
]

# Extended 10-view pool for auto-boost
_VIEWS10 = [
    "front view", "side profile view", "45 degree angle view",
    "top view overhead", "close-up macro detail view",
    "low angle hero shot", "three-quarter angle view",
    "45 degree right angled view", "front close-up view", "overhead angled view",
]

_BAD_DESC_STARTS = (
    "from side", "from above", "from the", "front view", "side view",
    "top view", "45 degree", "close-up", "low angle", "three-quarter",
)

# ══════════════════════════════════════════════════
# CORE HELPERS
# ══════════════════════════════════════════════════

def _item(cat, sub, prompt, subject_name=None):
    """Create a prompt item dict."""
    return {
        "category":     cat,
        "subcategory":  sub,
        "prompt":       prompt,
        "subject_name": subject_name or sub.replace("_", " ").title(),
        "seed":         random.randint(10000, 999999),
        "index":        0,
        "filename":     "img_000000.png",
        "status":       "pending",
    }

def dedup(items):
    """Remove duplicate prompts."""
    seen, out = set(), []
    for i in items:
        if i["prompt"] not in seen:
            seen.add(i["prompt"])
            out.append(i)
    return out

def _clean_descs(descriptions):
    """Remove descriptions that are just view directions."""
    clean = [d for d in descriptions
             if len(d.split()) > 4
             and not d.strip().lower().startswith(_BAD_DESC_STARTS)]
    return clean if clean else [descriptions[0]]

def expand_standard(cat, sub, descriptions, views=VIEWS_STD, suffix=BASE, subject_name=None):
    """
    FLUX-style expand — auto-boost to ≥10 base prompts per subcategory.
    Prompt = "A {description}, {view}, {suffix}"
    """
    descs = _clean_descs(descriptions)
    working_views = list(views)
    extra = [v for v in _VIEWS10 if v not in working_views]
    ei = 0
    while len(descs) * len(working_views) < 10 and ei < len(extra):
        working_views.append(extra[ei]); ei += 1
    items = []
    sname = subject_name or sub.replace("_", " ").title()
    for desc, view in iterproduct(descs, working_views):
        prompt = f"A {desc}, {view}, {suffix}"
        items.append(_item(cat, sub, prompt, sname))
    return dedup(items)

def expand_food(cat, sub, descriptions, views=VIEWS_FOOD, suffix=FOOD_BASE, subject_name=None):
    """
    FLUX-style food expand — natural serving descriptions.
    Prompt = "A single serving of {description}, {view}, {suffix}"
    """
    descs = _clean_descs(descriptions)
    working_views = list(views)
    extra_food = [
        "front view eye level", "45 degree angle view", "top view overhead flat lay",
        "low angle hero shot", "close-up macro detail view", "three-quarter angle view",
        "side profile view", "overhead birds eye view",
        "45 degree left angle view", "front close view",
    ]
    ei = 0
    while len(descs) * len(working_views) < 10:
        v = extra_food[ei % len(extra_food)]
        if v not in working_views:
            working_views.append(v)
        ei += 1
        if ei > 20:
            break
    items = []
    sname = subject_name or sub.replace("_", " ").title()
    for desc, view in iterproduct(descs, working_views):
        prompt = f"A single serving of {desc}, {view}, {suffix}"
        items.append(_item(cat, sub, prompt, sname))
    return dedup(items)

def expand_hero(cat, sub, descriptions, contexts,
                views=VIEWS_FOOD, suffix=FOOD_BASE, subject_name=None):
    """Hero items — more views, more contexts for popular items."""
    items = []
    sname = subject_name or sub.replace("_", " ").title()
    for desc, view in iterproduct(descriptions, views):
        items.append(_item(cat, sub, f"A single serving of {desc}, {view}, {suffix}", sname))
    for ctx, view in iterproduct(contexts, views[:3]):
        items.append(_item(cat, sub, f"A single {ctx}, {view}, {suffix}", sname))
    return dedup(items)

def expand_animal(cat, sub, descriptions, views=VIEWS_ANIMAL, suffix=ANIMAL_BASE, subject_name=None):
    """Animal prompts with correct anatomy emphasis."""
    descs = _clean_descs(descriptions)
    working_views = list(views)
    ei = 0
    extra = [v for v in _VIEWS10 if v not in working_views]
    while len(descs) * len(working_views) < 10 and ei < len(extra):
        working_views.append(extra[ei]); ei += 1
    items = []
    sname = subject_name or sub.replace("_", " ").title()
    for desc, view in iterproduct(descs, working_views):
        prompt = f"A {desc} in a natural pose, {view}, {suffix}"
        items.append(_item(cat, sub, prompt, sname))
    return dedup(items)

# ══════════════════════════════════════════════════
# CATEGORY 1: POULTRY & LIVE ANIMALS
# ══════════════════════════════════════════════════

POULTRY_ANIMALS = {
    "rooster": [
        "proud adult rooster with vivid red comb and colorful tail feathers",
        "rooster standing alert showing full plumage",
        "rooster with golden feathers and bright red wattle",
        "two roosters together showing size and plumage",
        "rooster and hen pair standing together",
        "rooster close-up portrait showing red comb detail",
        "three roosters group arranged naturally",
        "rooster crowing with beak open",
    ],
    "broiler_chicken": [
        "single white broiler chicken standing naturally",
        "broiler chicken full body side view",
        "two white broiler chickens together",
        "three broiler chickens group arranged",
        "broiler chicken close-up portrait",
        "flock of white broiler chickens together",
        "four broiler chickens arranged naturally",
    ],
    "goat": [
        "single brown goat standing with horns visible",
        "goat full body side view showing fur detail",
        "two goats together grazing pose",
        "young kid goat small and cute standing",
        "mother goat with baby kid together",
        "three goats group arranged",
        "goat close-up portrait showing face",
    ],
    "cow": [
        "single Indian cow with hump standing naturally",
        "cow full body side view showing markings",
        "two cows together arranged",
        "cow with calf standing together",
        "cow close-up portrait showing face",
        "three cows group arranged",
        "white cow standing front view",
    ],
    "hen": [
        "single brown hen standing naturally",
        "hen full body side view",
        "two hens together arranged",
        "hen with chicks arranged",
        "hen close-up portrait",
        "three hens group",
        "black hen standing naturally",
    ],
    "duck": [
        "single white duck standing naturally",
        "duck full body side view",
        "two ducks together arranged",
        "duck close-up portrait",
        "three ducks group",
    ],
    "rabbit": [
        "single white rabbit sitting naturally",
        "rabbit full body side view",
        "two rabbits together",
        "rabbit close-up portrait",
        "three rabbits grouped",
    ],
}

def gen_poultry_animals():
    items = []
    for sub, descs in POULTRY_ANIMALS.items():
        items += expand_animal("poultry_animals", sub, descs,
                               subject_name=sub.replace("_", " ").title())
    return items

# ══════════════════════════════════════════════════
# CATEGORY 2: FISH & SEAFOOD
# ══════════════════════════════════════════════════

FISH_SEAFOOD = {
    "whole_fish": [
        "single fresh Rohu fish whole with natural silver scales",
        "single whole Pomfret fish on a clean surface",
        "single Seer fish Vanjaram whole showing texture",
        "single Mackerel Ayala fish whole fresh",
        "single Tilapia fish whole with natural colors",
        "single Salmon fish whole showing pink flesh tones",
        "two Pomfret fish arranged side by side",
        "three Sardines arranged together on a tray",
        "three Mackerel fish arranged together fresh",
        "mixed fish variety arranged together on a surface",
        "pile of small fresh fish arranged naturally",
        "fish arranged on a banana leaf naturally",
        "four fish arranged in a neat row",
    ],
    "prawns_shrimp": [
        "single large fresh prawn whole with natural color",
        "three fresh prawns arranged together",
        "pile of fresh prawns on a clean surface",
        "prawns arranged on a banana leaf",
        "six tiger prawns arranged in a neat row",
        "mixed prawns pile fresh and glistening",
        "prawns in a steel bowl arranged",
        "single king prawn whole showing details",
    ],
    "crab": [
        "single whole crab with claws showing",
        "single mud crab whole from the front",
        "two crabs arranged together",
        "crab on a banana leaf",
        "three crabs group arranged",
        "crabs pile together fresh",
    ],
    "squid_other": [
        "single squid whole with tentacles visible",
        "two squid arranged together",
        "single lobster whole with claws",
        "mussels cluster arranged together",
        "mixed seafood variety arranged on a plate",
        "squid rings pile on plate",
    ],
}

FISH_CONTEXTS = [
    "on white surface", "on banana leaf", "on white plate",
    "on steel tray", "top view overhead", "side view",
]

def gen_fish_seafood():
    items = []
    for sub, descs in FISH_SEAFOOD.items():
        for desc, ctx in iterproduct(descs, FISH_CONTEXTS[:4]):
            prompt = f"A {desc}, {ctx}, {FOOD_BASE}"
            items.append(_item("fish_seafood", sub, prompt,
                               sub.replace("_", " ").title()))
    return dedup(items)

# ══════════════════════════════════════════════════
# CATEGORY 3: EGGS
# ══════════════════════════════════════════════════

EGGS = [
    "single fresh white egg on a clean surface",
    "single brown egg close-up showing texture",
    "three eggs arranged together neatly",
    "six eggs arranged in two rows",
    "eggs in a wicker basket",
    "cracked egg with yolk visible",
    "four eggs on a grey surface",
    "eggs in a small white ceramic bowl",
    "quail eggs small cluster naturally arranged",
    "six quail eggs with spotted shells arranged",
    "dozen eggs in a carton open",
    "two types of eggs arranged together",
    "eggs on a wooden surface natural setting",
    "pile of eggs arranged naturally",
]

def gen_eggs():
    items = []
    for desc in EGGS:
        for view in VIEWS_3:
            prompt = f"A {desc}, {view}, {FOOD_BASE}"
            items.append(_item("eggs", "eggs", prompt, "Egg"))
    return dedup(items)

# ══════════════════════════════════════════════════
# CATEGORY 4: FLOWERS
# ══════════════════════════════════════════════════

FLOWERS_SINGLE = {
    "rose": [
        "single red rose in full bloom with visible petals",
        "single pink rose with dew drops on petals",
        "single white rose with soft petals",
        "single yellow rose showing petal detail",
        "red rose bud before opening",
        "rose with green leaves attached",
        "rose close-up showing petal texture",
    ],
    "lotus": [
        "single pink lotus flower fully open",
        "single white lotus open with yellow center",
        "lotus bud before opening",
        "lotus flower with green leaf beside it",
    ],
    "jasmine": [
        "fresh white jasmine flower cluster on stem",
        "jasmine bunch with green leaves",
        "jasmine flowers close-up detail",
        "jasmine garland neatly arranged",
    ],
    "marigold": [
        "single bright orange marigold in full bloom",
        "single yellow marigold showing petals",
        "marigold close-up showing petal layers",
        "marigold bunch tied together",
    ],
    "sunflower": [
        "single sunflower with yellow petals and dark center",
        "sunflower close-up showing seed center detail",
        "sunflower with green stem and leaves",
        "sunflower bud before opening",
    ],
    "hibiscus": [
        "single red hibiscus fully open showing stamen",
        "single pink hibiscus in full bloom",
        "hibiscus close-up showing petal texture",
        "hibiscus with green leaves attached",
    ],
    "lily": [
        "single white lily with curved petals",
        "single pink lily in full bloom",
        "lily close-up showing spotted petals",
        "lily with green stem and leaves",
    ],
    "orchid": [
        "single purple orchid with delicate petals",
        "single white orchid elegant bloom",
        "orchid on stem with multiple flowers",
        "orchid close-up showing petal detail",
    ],
}

FLOWERS_GROUP = [
    "bunch of red roses arranged as a bouquet",
    "mixed colorful flower bouquet arranged",
    "five roses bouquet tied together",
    "marigold bunch tied with string",
    "jasmine and rose mixed bunch arranged",
    "three sunflowers together arranged",
    "lotus flowers two together on water",
    "mixed Indian festival flowers arranged",
    "wedding flower bouquet white and pink",
    "flower basket overflowing with colorful blooms",
    "temple flowers marigold and jasmine together",
    "fresh flowers flat lay arrangement overhead",
    "rose and jasmine garland arranged",
]

def gen_flowers():
    items = []
    for sub, descs in FLOWERS_SINGLE.items():
        for desc, view in iterproduct(descs, VIEWS_FLOWER):
            prompt = f"A {desc}, {view}, {BASE}"
            items.append(_item("flowers", sub, prompt,
                               sub.replace("_", " ").title()))
    for desc in FLOWERS_GROUP:
        for view in VIEWS_3:
            prompt = f"A {desc}, {view}, {BASE}"
            items.append(_item("flowers", "flower_groups", prompt, "Flowers"))
    return dedup(items)

# ══════════════════════════════════════════════════
# CATEGORY 5: FRUITS
# ══════════════════════════════════════════════════

FRUITS_SINGLE = {
    "mango":        ["single ripe yellow mango whole", "mango cut in half showing orange flesh", "mango sliced showing juicy flesh", "mango with green leaf attached", "green mango whole"],
    "banana":       ["single yellow banana", "single banana slightly peeled showing flesh", "green banana whole", "single banana close-up showing texture"],
    "apple":        ["single red apple whole with stem", "apple cut in half showing white flesh", "single green apple whole", "apple with water droplets on skin"],
    "watermelon":   ["whole round watermelon", "watermelon slice showing red flesh and seeds", "watermelon half showing flesh", "watermelon cubes arranged"],
    "grapes":       ["bunch of purple grapes on vine", "bunch of green grapes", "grapes close-up showing round form"],
    "orange":       ["single orange whole with peel texture", "orange cut in half showing segments", "orange slice round showing segments"],
    "lemon":        ["single yellow lemon whole", "lemon cut in half showing flesh", "lemon with green leaf attached"],
    "coconut":      ["green tender coconut whole", "coconut with straw inserted", "mature brown coconut whole", "coconut cut open showing white flesh"],
    "papaya":       ["whole ripe papaya orange skin", "papaya cut in half showing orange flesh and seeds", "papaya slices arranged"],
    "pomegranate":  ["whole pomegranate with crown", "pomegranate cut in half showing red seeds", "pomegranate seeds scattered"],
    "pineapple":    ["whole pineapple with crown leaves", "pineapple slice round showing pattern"],
    "guava":        ["single white guava whole", "guava cut in half showing pink flesh", "guava with leaf attached"],
    "other_fruits": [
        "single fresh strawberry with green top", "kiwi cut in half showing green flesh",
        "dragon fruit cut in half showing white flesh", "fig cut in half showing pink interior",
        "fresh chikoo sapodilla whole", "custard apple whole with bumpy skin",
        "single red plum whole", "two cherries with stems together",
    ],
}

FRUITS_GROUP = [
    "three ripe mangoes arranged together",
    "mango pile heap naturally arranged",
    "bunch of six bananas together",
    "three apples arranged naturally",
    "two oranges one sliced beside",
    "three lemons arranged together",
    "watermelon with a slice cut beside it",
    "three guavas arranged together",
    "grapes and apples together",
    "mixed fruit basket overflowing",
    "tropical fruits arranged collection",
    "fruit platter with cut fruits arranged",
    "mixed Indian fruits variety together",
    "two pineapples arranged together",
    "strawberries pile arranged",
]

FRUIT_CONTEXTS = [
    "on a clean white surface", "on a wooden surface",
    "top view overhead flat lay", "close-up showing texture",
    "with fresh water droplets",
]

def gen_fruits():
    items = []
    for sub, descs in FRUITS_SINGLE.items():
        for desc, ctx in iterproduct(descs, FRUIT_CONTEXTS):
            prompt = f"A {desc}, {ctx}, {FOOD_BASE}"
            items.append(_item("fruits", sub, prompt,
                               sub.replace("_", " ").title()))
    for desc in FRUITS_GROUP:
        for view in VIEWS_3:
            prompt = f"{desc.capitalize()}, {view}, {FOOD_BASE}"
            items.append(_item("fruits", "fruit_groups", prompt, "Fruits"))
    return dedup(items)

# ══════════════════════════════════════════════════
# CATEGORY 6: VEGETABLES
# ══════════════════════════════════════════════════

VEGS_SINGLE = {
    "tomato":       ["single ripe red tomato whole with stem", "tomato cut in half showing seeds", "tomato slice round", "cluster of cherry tomatoes"],
    "potato":       ["single brown potato whole", "potato cut in half showing white flesh", "baby potatoes cluster"],
    "sweet_potato": ["single orange sweet potato whole", "sweet potato cut in half showing orange flesh"],
    "brinjal":      ["single purple brinjal whole", "long green brinjal whole", "brinjal cut in half showing flesh"],
    "onion":        ["single onion whole with dry skin", "onion cut in half showing layers", "small shallots cluster", "spring onion bunch tied"],
    "carrot":       ["single orange carrot whole with top leaves", "carrot slice rounds", "baby carrots bunch tied"],
    "capsicum":     ["single green capsicum whole", "single red capsicum whole", "single yellow capsicum whole", "capsicum cut in half"],
    "okra":         ["single okra pod whole", "okra bunch fresh arranged", "okra cut showing cross-section"],
    "cucumber":     ["single green cucumber whole", "cucumber sliced in rounds", "cucumber cut in half lengthwise"],
    "beans":        ["green beans bunch fresh tied", "beans close-up showing texture"],
    "other_veggies": [
        "whole cauliflower with green leaves", "broccoli head whole fresh",
        "round cabbage whole", "bitter gourd whole with ridges",
        "fresh ginger root showing texture", "garlic bulb whole",
        "spinach bunch fresh", "whole pumpkin orange",
    ],
}

VEGS_GROUP = [
    "three tomatoes arranged together",
    "tomatoes in a small ceramic bowl",
    "three brinjals arranged together",
    "pile of potatoes naturally arranged",
    "three onions arranged together",
    "three carrots arranged with tops",
    "three cucumbers arranged together",
    "three capsicums in mixed colors together",
    "okra bunch arranged naturally",
    "mixed vegetables flat lay arrangement",
    "Indian cooking vegetables arranged together",
    "vegetable basket overflowing fresh",
    "garlic onion ginger together arranged",
    "mixed green vegetables bunch",
    "all vegetables flat lay collection",
]

VEG_CONTEXTS = [
    "on a clean white surface", "on a wooden surface",
    "top view overhead flat lay", "close-up showing texture",
    "with fresh water droplets on skin",
]

def gen_vegetables():
    items = []
    for sub, descs in VEGS_SINGLE.items():
        for desc, ctx in iterproduct(descs, VEG_CONTEXTS):
            prompt = f"A {desc}, {ctx}, {FOOD_BASE}"
            items.append(_item("vegetables", sub, prompt,
                               sub.replace("_", " ").title()))
    for desc in VEGS_GROUP:
        for view in VIEWS_3:
            prompt = f"{desc.capitalize()}, {view}, {FOOD_BASE}"
            items.append(_item("vegetables", "veg_groups", prompt, "Vegetables"))
    return dedup(items)

# ══════════════════════════════════════════════════
# CATEGORY 7: COOL DRINKS
# ══════════════════════════════════════════════════

COOL_DRINKS = {
    "mojito": [
        "mojito in a tall clear glass with fresh mint leaves and lime slice",
        "mint mojito with crushed ice and lime wedge in glass",
        "strawberry mojito with red color and mint garnish",
        "mango mojito yellow drink in tall glass with straw",
        "two mojito glasses side by side",
        "mojito in a mason jar with mint and ice",
    ],
    "lemon_soda": [
        "fresh lemon soda in a glass with ice and lemon slice",
        "nimbu pani lime water in glass with salt rim",
        "masala lemon soda in tall glass with spices",
        "lemon soda with condensation on glass",
        "two lemon soda glasses together",
    ],
    "lassi": [
        "mango lassi in a tall glass with frothy top and mango slices",
        "sweet plain lassi in a brass glass with cream on top",
        "rose lassi pink color in a glass with rose petals",
        "lassi in a clay kulhad traditional style",
        "two lassi glasses side by side",
    ],
    "tender_coconut": [
        "green tender coconut with straw inserted",
        "tender coconut cut open showing white flesh and water",
        "coconut water in a glass with coconut beside it",
        "two tender coconuts arranged together",
        "three green coconuts arranged",
    ],
    "fresh_juice": [
        "fresh orange juice in glass with orange slice on rim",
        "sugarcane juice in glass green color",
        "watermelon juice red color in glass with straw",
        "pomegranate juice deep red in glass",
        "carrot juice orange color in glass",
        "two fresh juice glasses side by side",
    ],
    "buttermilk": [
        "buttermilk in a glass with curry leaves garnish",
        "masala buttermilk in a brass tumbler",
        "buttermilk in a clay pot traditional",
        "frothy buttermilk in glass with tempering",
        "two buttermilk glasses together",
    ],
}

def gen_drinks():
    items = []
    for sub, descs in COOL_DRINKS.items():
        for desc in descs:
            for view in VIEWS_FOOD[:3]:
                prompt = f"A {desc}, {view}, {FOOD_BASE}"
                items.append(_item("cool_drinks", sub, prompt,
                                   sub.replace("_", " ").title()))
    return dedup(items)

# ══════════════════════════════════════════════════
# CATEGORY 8: INDIAN FOODS
# ══════════════════════════════════════════════════

INDIAN_FOODS = {
    "biryani": [
        "Chicken Biryani with whole chicken leg piece and long grain saffron rice in a round steel plate",
        "Chicken Biryani with bone-in chicken and golden saffron rice garnished with fried onions in copper handi",
        "Hyderabadi Dum Biryani with juicy chicken and aromatic rice in a wide ceramic bowl",
        "Mutton Biryani with tender mutton pieces and fragrant basmati rice in steel bowl",
        "Biryani steaming hot served on a banana leaf with raita beside",
        "Biryani in open clay pot showing layers of rice and meat",
        "Prawn Biryani with large prawns and saffron rice in wide bowl",
        "Egg Biryani with halved boiled eggs and basmati rice on plate",
    ],
    "dosa": [
        "crispy masala dosa folded in a half-moon shape with sambar and coconut chutney on plate",
        "crispy plain dosa golden brown served on banana leaf",
        "ghee roast dosa with shiny butter coating deep golden on plate",
        "paper thin crispy dosa extra long on a large tray",
        "set dosa soft fluffy stack of three on steel plate with chutneys",
        "egg dosa with egg filling golden brown on plate",
        "cheese dosa with melted cheese visible inside",
    ],
    "idly": [
        "four soft white idly on a steel plate with sambar and coconut chutney",
        "idly on banana leaf with sambar bowl beside",
        "mini idly in sambar bowl floating",
        "idly stack on plate with podi powder and ghee",
        "idly close-up showing soft texture",
        "idly with three chutneys arranged beside",
    ],
    "parotta": [
        "layered parotta on banana leaf with salna curry",
        "parotta on plate showing flaky layers",
        "kothu parotta on plate shredded and spiced",
        "parotta stack showing crispy layers",
        "parotta with egg on plate",
    ],
    "curry": [
        "chicken curry in a brown ceramic bowl with curry leaves garnish",
        "mutton curry in a clay pot with steam rising",
        "fish curry in a bowl with red color and curry leaves",
        "egg curry in a bowl with boiled eggs visible",
        "prawn curry in bowl with prawns visible",
        "thick Chettinad curry in steel bowl",
        "curry with rice on a banana leaf",
    ],
    "rice_dishes": [
        "lemon rice on banana leaf with curry leaves and peanuts",
        "curd rice in a bowl with cucumber and pomegranate",
        "tomato rice on plate with fried onions",
        "pongal in a clay bowl with ghee poured on top",
        "sambar rice on plate",
        "coconut rice on banana leaf",
        "tamarind puliyodharai rice on plate",
    ],
    "snacks": [
        "samosa on plate with green chutney",
        "medu vada on plate golden brown",
        "murukku on plate traditional crunchy",
        "pakora golden brown in a plate",
        "banana chips on plate crispy",
        "masala vada on plate",
        "snacks platter arranged with variety",
    ],
}

def gen_indian_food():
    items = []
    for sub, descs in INDIAN_FOODS.items():
        ctx_descs = [f"{d}, {ctx}" for d, ctx in
                     iterproduct(descs[:4], ["in a bowl", "on a plate", "on banana leaf"])]
        items += expand_food("food_indian", sub, descs + ctx_descs,
                             subject_name=sub.replace("_", " ").title())
    return items

# ══════════════════════════════════════════════════
# CATEGORY 9: WORLD FOODS
# ══════════════════════════════════════════════════

WORLD_FOODS = {
    "pizza":         ["whole pizza on wooden board with melted cheese and toppings", "pizza slice showing cheese stretch", "mini pizza on plate", "pizza freshly baked with steam"],
    "burger":        ["burger whole on plate with sesame bun and fillings", "burger cut in half showing layers of meat and vegetables", "double burger towering with toppings"],
    "fried_chicken": ["crispy fried chicken drumstick on plate", "fried chicken pieces in a bucket", "fried chicken strips on plate", "four crispy fried chicken pieces"],
    "french_fries":  ["french fries in a red box", "french fries in a paper cone", "crispy waffle fries on plate", "large fries with dipping sauce"],
    "noodles":       ["ramen bowl with egg soft-boiled and bamboo shoots", "stir fried noodles in a bowl with vegetables", "noodle bowl with steam rising and chopsticks"],
    "fried_rice":    ["fried rice in a bowl with spring onion garnish", "egg fried rice on plate with chopsticks", "vegetable fried rice in wok"],
    "chinese":       ["spring rolls on plate with sweet chili sauce", "dim sum in bamboo basket steaming", "chicken manchurian in bowl with gravy", "chow mein noodles in bowl"],
}

def gen_world_food():
    items = []
    for sub, descs in WORLD_FOODS.items():
        items += expand_food("food_world", sub, descs,
                             subject_name=sub.replace("_", " ").title())
    return items

# ══════════════════════════════════════════════════
# CATEGORY 10: DAIRY PRODUCTS
# ══════════════════════════════════════════════════

DAIRY = {
    "milk":         ["full glass of white milk", "milk pouring into a glass showing splash", "milk bottle sealed", "milk in a steel glass"],
    "curd_yogurt":  ["curd in a clay pot showing white creamy texture", "yogurt in a glass jar with spoon", "curd in a white bowl with tempering on top", "two bowls of curd arranged"],
    "butter_ghee":  ["butter block on white plate showing creamy texture", "ghee in a glass jar golden color", "ghee close-up showing golden clarity", "butter on wooden board with knife"],
    "paneer":       ["paneer block whole on plate", "paneer cubes arranged on a plate", "paneer cut in half showing white interior", "fresh paneer on banana leaf"],
    "cheese":       ["cheese block whole on wooden board", "cheese slices arranged on plate", "cheese cubes arranged neatly", "mozzarella cheese ball fresh"],
}

def gen_dairy():
    items = []
    for sub, descs in DAIRY.items():
        items += expand_food("dairy_products", sub, descs,
                             subject_name=sub.replace("_", " ").title())
    return items

# ══════════════════════════════════════════════════
# CATEGORY 11: DRY FRUITS & NUTS
# ══════════════════════════════════════════════════

DRY_FRUITS_SINGLE = [
    "cashew nuts on a white plate showing ivory color",
    "whole almonds on a white plate",
    "pistachios with shells on a plate",
    "walnuts showing brain-like texture",
    "dark raisins pile on plate",
    "dates dried on a white plate",
    "dried figs showing texture",
    "dried apricots orange color on plate",
    "roasted peanuts pile on plate",
    "pine nuts small and golden on plate",
    "hazelnuts on plate",
    "mixed dry fruits on a wooden board",
    "sunflower seeds on plate",
]

DRY_FRUITS_GROUP = [
    "cashews and almonds mixed on a plate",
    "mixed dry fruits variety in a bowl",
    "mixed nuts in a wooden bowl",
    "dry fruits in three small bowls arranged",
    "cashew almond pistachio together on plate",
    "dry fruits flat lay collection on wooden board",
    "nuts and seeds mixed in a bowl",
    "dry fruits in a glass jar",
    "assorted dry fruits platter arranged",
    "all nuts variety flat lay collection",
    "dry fruits gift box open showing variety",
]

def gen_dry_fruits():
    items = []
    for desc in DRY_FRUITS_SINGLE:
        for view in VIEWS_STD[:3]:
            prompt = f"A {desc}, {view}, {FOOD_BASE}"
            items.append(_item("dry_fruits_nuts", "dry_fruits", prompt, "Dry Fruits"))
    for desc in DRY_FRUITS_GROUP:
        for view in VIEWS_3:
            prompt = f"{desc.capitalize()}, {view}, {FOOD_BASE}"
            items.append(_item("dry_fruits_nuts", "nuts_group", prompt, "Nuts"))
    return dedup(items)

# ══════════════════════════════════════════════════
# CATEGORY 12: BAKERY & SNACKS
# ══════════════════════════════════════════════════

BAKERY = {
    "bread":           ["bread loaf whole showing golden crust", "bread slices arranged showing white interior", "pav bread rolls arranged", "whole grain bread loaf on wooden board"],
    "cake":            ["whole round chocolate cake with frosting", "cake slice on plate showing layers", "birthday cake with candles lit", "three cupcakes arranged with frosting"],
    "biscuits_cookies":["biscuits pile on a white plate", "cookies arranged on plate showing chocolate chips", "biscuits in a glass jar", "three cookies arranged on plate"],
    "snacks":          ["potato chips in a bowl showing crispy texture", "popcorn in a bowl white and fluffy", "mixed snacks in a bowl", "nachos in bowl with sauce"],
}

BAKERY_CONTEXTS = [
    "on a clean white surface", "on a wooden board",
    "top view overhead", "close-up showing texture",
]

def gen_bakery():
    items = []
    for sub, descs in BAKERY.items():
        for desc, ctx in iterproduct(descs, BAKERY_CONTEXTS):
            prompt = f"A {desc}, {ctx}, {FOOD_BASE}"
            items.append(_item("bakery_snacks", sub, prompt,
                               sub.replace("_", " ").title()))
    return dedup(items)

# ══════════════════════════════════════════════════
# CATEGORY 13: AYURVEDIC / HERBAL
# ══════════════════════════════════════════════════

AYURVEDA = {
    "plants_leaves": [
        "fresh neem leaves bunch showing green color",
        "tulsi holy basil plant with leaves",
        "aloe vera plant showing thick leaves",
        "fresh curry leaves bunch on stem",
        "fresh mint leaves bunch",
        "moringa drumstick leaves bunch",
        "brahmi leaves fresh showing round shape",
    ],
    "herbs_roots": [
        "fresh turmeric root showing yellow interior",
        "turmeric powder in a small bowl bright yellow",
        "fresh ginger root showing texture",
        "cinnamon sticks bundle tied together",
        "black pepper pile whole",
        "green cardamom pods pile",
        "cloves pile whole aromatic",
        "star anise whole showing star shape",
        "fenugreek seeds in a small bowl",
    ],
    "products": [
        "ayurvedic oil bottle on white surface",
        "herbal powder in a clay bowl",
        "mortar and pestle with herbs",
        "herbal oil in a glass bottle",
        "ayurvedic capsules arranged on plate",
        "natural herbal soap bar",
    ],
    "group": [
        "turmeric ginger neem arranged together on surface",
        "ayurvedic herbs flat lay collection",
        "herbal roots arranged naturally",
        "three ayurvedic bottles arranged",
        "herbs in small bowls arranged",
        "five herbal ingredients arranged together",
    ],
}

AYUR_CONTEXTS = [
    "on a white surface", "on a wooden surface",
    "top view overhead", "close-up showing detail",
]

def gen_ayurveda():
    items = []
    for sub, descs in AYURVEDA.items():
        for desc, ctx in iterproduct(descs, AYUR_CONTEXTS):
            prompt = f"A {desc}, {ctx}, {BASE}"
            items.append(_item("ayurvedic_herbal", sub, prompt,
                               sub.replace("_", " ").title()))
    return dedup(items)

# ══════════════════════════════════════════════════
# CATEGORY 14: INDIAN SWEETS
# ══════════════════════════════════════════════════

INDIAN_SWEETS_SINGLE = [
    "mysore pak golden square piece on plate",
    "gulab jamun in sugar syrup in a bowl",
    "jalebi orange spiral on a plate",
    "carrot gajar halwa in a bowl with ghee",
    "round ladoo on a plate",
    "kaju katli diamond shaped pieces on plate",
    "barfi pieces on a silver plate",
    "rasgulla in sugar syrup in a bowl",
    "kheer in a clay bowl with saffron",
    "payasam in a silver bowl",
    "rava kesari in a bowl with ghee",
    "coconut burfi on a plate",
    "modak on a plate",
    "peda on a plate arranged",
]

INDIAN_SWEETS_GROUP = [
    "four gulab jamun in bowl with syrup",
    "jalebi pile on a plate orange and crispy",
    "five round ladoo arranged on plate",
    "kaju katli pieces arranged on plate",
    "mixed Indian sweets platter arranged",
    "Indian mithai variety on a silver plate",
    "festival Diwali sweets collection plate",
    "sweets on a banana leaf arranged",
    "assorted Indian sweets in a box open",
    "ten variety sweets flat lay collection",
]

SWEET_CONTEXTS = [
    "on a white plate", "on a silver plate", "on banana leaf",
    "in a ceramic bowl", "top view overhead", "close-up detail",
]

def gen_sweets():
    items = []
    for desc in INDIAN_SWEETS_SINGLE:
        for ctx in SWEET_CONTEXTS[:3]:
            prompt = f"A {desc}, {ctx}, {FOOD_BASE}"
            items.append(_item("indian_sweets", "sweets", prompt, "Indian Sweets"))
    for desc in INDIAN_SWEETS_GROUP:
        for view in VIEWS_3:
            prompt = f"{desc.capitalize()}, {view}, {FOOD_BASE}"
            items.append(_item("indian_sweets", "sweets_group", prompt, "Indian Sweets"))
    return dedup(items)

# ══════════════════════════════════════════════════
# CATEGORY 15: STATIONERY
# ══════════════════════════════════════════════════

STATIONERY_GROUPS = [
    "pencils eraser and sharpener arranged together",
    "notebooks and pens arranged in a flat lay",
    "school bag with books and pencil box",
    "ruler scale compass and protractor together",
    "color pencils set arranged in fan shape",
    "pen pencil ruler and eraser flat lay",
    "geometry box open with instruments showing",
    "crayons set arranged in colorful fan",
    "watercolor paint set with brushes arranged",
    "marker pens set arranged by color",
    "school books stack neatly arranged",
    "pencil box open with stationery inside",
    "scissors glue tape and stapler together",
    "highlighter pens set arranged colorful",
    "drawing book and sketching pencils together",
    "all stationery items flat lay collection",
    "backpack open with stationery items",
    "chalk pieces and blackboard duster together",
    "clipboard with paper and pen",
    "stationery items in pencil stand arranged",
]

def gen_stationery():
    items = []
    views = ["flat lay top view", "45 degree angle", "front view", "close-up detail"]
    for desc in STATIONERY_GROUPS:
        for view in views:
            prompt = f"{desc.capitalize()}, {view}, {BASE}"
            items.append(_item("stationery", "stationery_groups", prompt, "Stationery"))
    return dedup(items)

# ══════════════════════════════════════════════════
# CATEGORY 16: KITCHEN VESSELS
# ══════════════════════════════════════════════════

KITCHEN_GROUPS = [
    "steel kadai and spatula together on surface",
    "pressure cooker and steel vessel together",
    "three steel vessels stacked together",
    "clay pot and steel pot together arranged",
    "steel thali and bowl set arranged",
    "cooking pots and pans set flat lay",
    "steel kadai tawa and ladle together",
    "three clay pots different sizes arranged",
    "kitchen vessel set flat lay collection",
    "steel bowls nested set arranged",
    "cast iron pan and steel ladle together",
    "copper vessel and brass vessel together",
    "steel water pot and steel glass together",
    "five kitchen vessels arranged together",
    "tawa griddle and rolling pin together",
    "mixing bowls three sizes nested",
    "wok pan and wooden spatula together",
    "pressure cooker set with whistle visible",
    "clay cooking pot and wooden spoon",
    "steel cookware set flat lay",
    "brass vessel and copper pot together",
    "kitchen utensils full set flat lay",
    "steel vessel with lid and ladle together",
    "four different sized pots arranged",
    "Indian kitchen vessels collection",
    "non-stick pan and steel pan together",
    "vessel steamer and pressure cooker together",
    "steel tiffin box set stacked",
    "water bottle and steel glass together",
    "complete kitchen vessel set arranged",
]

def gen_kitchen():
    items = []
    views = ["flat lay top view", "45 degree angle", "front view",
             "overhead view", "close-up detail", "side view"]
    for desc in KITCHEN_GROUPS:
        for view in views:
            prompt = f"{desc.capitalize()}, {view}, {BASE}"
            items.append(_item("kitchen_vessels", "kitchen_groups", prompt, "Kitchen Vessels"))
    return dedup(items)

# ══════════════════════════════════════════════════
# CATEGORY 17: MOBILE ACCESSORIES
# ══════════════════════════════════════════════════

MOBILE_ACCESSORIES = {
    "smartphones": [
        "iPhone 15 Pro showing front screen and camera island",
        "Samsung Galaxy S24 Ultra front view with curved screen",
        "OnePlus 12 front view clean design",
        "Redmi Note 13 Pro front view",
        "Vivo V30 Pro front view",
        "OPPO Reno 11 front view",
        "Nothing Phone 2 with transparent back",
        "Google Pixel 8 front view",
        "two smartphones side by side arranged",
        "three smartphones arranged together",
    ],
    "earphones": [
        "Apple AirPods Pro in charging case open",
        "Samsung Galaxy Buds in case top view",
        "Sony WF-1000XM5 earbuds in case",
        "Boat Airdopes earbuds in case open",
        "JBL wireless earbuds in case",
        "two earbuds and open case arranged together",
        "earbuds case closed front view",
    ],
    "chargers_cables": [
        "Apple 20W USB-C charger adapter on surface",
        "Samsung fast charger adapter front view",
        "USB-C charging cable neatly coiled",
        "wireless charger pad flat on surface",
        "MagSafe charger Apple round pad",
        "Anker charger adapter front view",
        "charging cable flat lay arranged",
    ],
    "phone_cases": [
        "clear transparent iPhone case front view",
        "Samsung phone case front view",
        "three phone cases arranged together",
        "silicone phone case side view",
        "leather phone case front view",
        "phone case back view showing design",
    ],
    "powerbanks": [
        "Anker power bank front view sleek design",
        "Mi power bank 20000mAh front view",
        "power bank with charging cable connected",
        "two power banks arranged together",
        "power bank top view flat lay",
    ],
    "group": [
        "iPhone with AirPods Pro together flat lay",
        "smartphone charger and cable together",
        "mobile accessories flat lay collection",
        "phone case power bank earbuds arranged",
        "two phones side by side comparison",
        "mobile setup flat lay complete",
    ],
}

MOBILE_CONTEXTS = [
    "on a white surface", "on a grey surface",
    "top view flat lay", "45 degree angle", "close-up detail",
]

def gen_mobile():
    items = []
    for sub, descs in MOBILE_ACCESSORIES.items():
        for desc, ctx in iterproduct(descs, MOBILE_CONTEXTS):
            prompt = f"A {desc}, {ctx}, {BASE}"
            items.append(_item("mobile_accessories", sub, prompt,
                               sub.replace("_", " ").title()))
    return dedup(items)

# ══════════════════════════════════════════════════
# CATEGORY 18: COMPUTER ACCESSORIES
# ══════════════════════════════════════════════════

COMPUTER_ACCESSORIES = {
    "laptops": [
        "MacBook Air M2 open showing aluminium body and screen",
        "MacBook Pro 14 open showing notch and keyboard",
        "Dell XPS 13 open front view thin bezel",
        "HP Spectre x360 open elegant design",
        "Lenovo ThinkPad open front view classic design",
        "ASUS ZenBook open front view compact design",
        "laptop closed showing slim profile side view",
        "laptop top view flat lay closed",
        "two laptops arranged together comparison",
    ],
    "keyboards_mouse": [
        "Apple Magic Keyboard top view white slim",
        "Apple Magic Mouse side view white",
        "Apple keyboard and Magic Mouse together flat lay",
        "Logitech MX Keys keyboard top view backlit",
        "Logitech MX Master mouse side view ergonomic",
        "mechanical keyboard with RGB lighting top view",
        "wireless keyboard top view flat lay",
        "keyboard and mouse flat lay together",
    ],
    "monitors": [
        "Dell monitor front view thin bezel",
        "LG UltraWide monitor front view curved",
        "Samsung curved monitor front view",
        "Apple Studio Display front view",
        "monitor side profile view",
        "gaming monitor front view with RGB",
        "two monitors arranged together",
    ],
    "headphones": [
        "Sony WH-1000XM5 headphones front view folded",
        "Apple AirPods Max over-ear headphones",
        "Bose QuietComfort headphones side view",
        "JBL over-ear headphones front view",
        "headphones flat lay top view",
        "headphones side profile view",
        "Sennheiser headphones front view",
    ],
    "other_accessories": [
        "USB-C hub multiport adapter on surface",
        "Samsung T7 external SSD on surface",
        "Western Digital external hard drive front view",
        "Logitech C920 webcam front view",
        "large desk mouse pad flat lay",
        "laptop accessories flat lay collection",
    ],
    "group": [
        "MacBook with Apple keyboard and mouse arranged flat lay",
        "laptop keyboard mouse and headphones flat lay",
        "monitor keyboard and mouse arranged setup",
        "gaming setup monitor keyboard mouse headphones",
        "laptop accessories collection flat lay",
        "full computer desk setup aerial view",
    ],
}

COMPUTER_CONTEXTS = [
    "on a white surface", "flat lay top view",
    "45 degree angle view", "front view", "close-up detail",
]

def gen_computer():
    items = []
    for sub, descs in COMPUTER_ACCESSORIES.items():
        for desc, ctx in iterproduct(descs, COMPUTER_CONTEXTS):
            prompt = f"A {desc}, {ctx}, {BASE}"
            items.append(_item("computer_accessories", sub, prompt,
                               sub.replace("_", " ").title()))
    return dedup(items)

# ══════════════════════════════════════════════════
# CATEGORY 19: FOOTWEAR
# ══════════════════════════════════════════════════

FOOTWEAR = {
    "chappals":     ["single leather chappal side view", "pair of chappals front view", "rubber chappal pair top view", "traditional chappal side view", "chappal sole view showing pattern"],
    "sandals":      ["single strappy sandal side view", "pair of sandals front view", "ladies sandal pair top view flat lay", "leather sandal close-up detail", "two sandals arranged"],
    "shoes":        ["single formal leather shoe side view", "pair of shoes front view", "shoes side by side top view", "leather shoe close-up showing grain", "shoe sole view"],
    "heels":        ["single stiletto heel side view", "pair of heels front view", "block heel shoe pair top view", "ladies heels arranged", "pointed heel close-up"],
    "sports_shoes": ["single running shoe side view", "pair of sports shoes front view", "sneakers side by side top view", "sports shoe sole detail close-up", "running shoes 45 degree"],
    "kids":         ["kids school shoes pair front view", "children sneakers front view", "baby shoes tiny pair top view", "kids sandal pair arranged"],
}

SHOE_VIEWS = [
    "side profile view", "front view", "top view flat lay",
    "45 degree angle", "sole view", "close-up detail",
]

def gen_footwear():
    items = []
    for sub, descs in FOOTWEAR.items():
        for desc, view in iterproduct(descs, SHOE_VIEWS):
            prompt = f"A {desc}, {view}, {BASE}"
            items.append(_item("footwear", sub, prompt,
                               sub.replace("_", " ").title()))
    return dedup(items)

# ══════════════════════════════════════════════════
# CATEGORY 20: INDIAN DRESS
# ══════════════════════════════════════════════════

INDIAN_DRESS = {
    "saree": [
        "silk saree neatly folded showing zari border",
        "Kanchipuram saree folded showing gold border",
        "Banarasi saree folded showing embroidery",
        "cotton saree folded showing print",
        "bridal saree folded showing heavy embroidery",
        "saree draped showing fabric texture",
        "saree border close-up showing embroidery detail",
    ],
    "salwar_kameez": [
        "salwar kameez set flat lay showing embroidery",
        "anarkali suit flat lay full length",
        "salwar kameez on hanger full view",
        "printed salwar kameez flat lay",
        "palazzo suit flat lay",
        "salwar kameez embroidery close-up",
    ],
    "lehenga": [
        "bridal lehenga folded showing embroidery",
        "lehenga choli set flat lay",
        "lehenga fabric detail close-up",
        "lehenga top view showing embroidery",
    ],
    "kurta": [
        "mens kurta folded flat lay showing print",
        "embroidered kurta flat lay",
        "silk kurta folded",
        "kurta pajama set arranged flat lay",
        "sherwani flat lay showing embroidery",
    ],
    "kids_dress": [
        "kids lehenga choli flat lay",
        "kids kurta pajama flat lay",
        "baby girl frock flat lay",
        "boys sherwani flat lay",
        "children traditional festive wear flat lay",
    ],
}

DRESS_CONTEXTS = [
    "neatly folded on a clean surface", "flat lay top view",
    "hanging full length", "fabric embroidery detail close-up",
    "fabric texture close-up",
]

def gen_dress():
    items = []
    for sub, descs in INDIAN_DRESS.items():
        for desc, ctx in iterproduct(descs, DRESS_CONTEXTS):
            prompt = f"A {desc}, {ctx}, {BASE}"
            items.append(_item("indian_dress", sub, prompt,
                               sub.replace("_", " ").title()))
    return dedup(items)

# ══════════════════════════════════════════════════
# CATEGORY 21: JEWELLERY MODELS
# ══════════════════════════════════════════════════

JEWELLERY_MODELS = {
    "necklace": [
        "Indian woman wearing gold necklace",
        "South Indian woman with temple gold necklace",
        "woman with layered gold necklace in saree",
        "woman gold necklace three quarter portrait",
        "bridal gold necklace model close-up portrait",
        "woman wearing heavy gold jewelry portrait",
    ],
    "bridal": [
        "South Indian bride with full gold jewellery portrait",
        "Indian bride in silk saree with gold jewellery set",
        "Tamil bride with temple jewellery portrait",
        "bridal close-up face portrait with gold jewelry",
        "Kerala bride with gold jewellery portrait",
        "North Indian bride with gold jewellery portrait",
    ],
    "earrings": [
        "woman wearing gold jhumka earrings portrait",
        "woman with gold hoop earrings portrait",
        "woman with chandelier earrings side view",
        "Indian woman gold kammal earrings close-up",
        "woman with long gold earrings portrait",
    ],
    "bangles": [
        "woman hands with gold bangles close-up",
        "Indian woman bridal bangles wrist close-up",
        "woman hands with glass and gold bangles",
        "woman gold kada bangle wrist close-up",
        "woman multiple bangles portrait hands",
    ],
}

MODEL_LOOKS = [
    "elegant studio portrait", "natural smile portrait",
    "side profile portrait", "three quarter portrait",
    "close-up face portrait", "full upper body portrait",
]

MODEL_SAREE_LIST = [
    "in a silk saree", "in a bridal saree",
    "in a South Indian saree", "in a Kanchipuram silk saree",
]

def gen_jewellery_models():
    items = []
    for sub, descs in JEWELLERY_MODELS.items():
        for desc in descs:
            saree = random.choice(MODEL_SAREE_LIST)
            for look in MODEL_LOOKS:
                prompt = (
                    f"A professional studio portrait of an {desc} {saree}, "
                    f"{look}, {MODEL_BASE}"
                )
                items.append(_item("jewellery_models", sub, prompt, "Jewellery Model"))
    return dedup(items)

# ══════════════════════════════════════════════════
# CATEGORY 22: OFFICE MODELS
# ══════════════════════════════════════════════════

OFFICE_MODELS = {
    "women": [
        "Indian woman in formal office blazer",
        "professional woman in formal suit confident",
        "businesswoman in formal corporate attire",
        "office woman in formal saree professional",
        "woman in formal white shirt business look",
        "Indian businesswoman confident corporate pose",
    ],
    "men": [
        "Indian man in formal business suit",
        "businessman in formal shirt and trousers",
        "professional man in blazer corporate look",
        "corporate man in suit and tie",
        "Indian professional man formal portrait",
        "man in formal white shirt business portrait",
    ],
    "casual": [
        "Indian woman in smart casual kurta and jeans",
        "woman in modern printed western top",
        "young woman in smart casual office wear",
        "Indian girl in modern casual professional look",
    ],
}

OFFICE_POSES = [
    "full body standing portrait", "side profile portrait",
    "three quarter portrait", "arms crossed professional pose",
    "natural smile portrait", "headshot close-up portrait",
]

def gen_office_models():
    items = []
    for sub, descs in OFFICE_MODELS.items():
        for desc, pose in iterproduct(descs, OFFICE_POSES):
            prompt = (
                f"A studio portrait of an {desc}, {pose}, "
                f"{MODEL_BASE}"
            )
            items.append(_item("office_models", sub, prompt, "Office Model"))
    return dedup(items)

# ══════════════════════════════════════════════════
# CATEGORY 23: VEHICLES
# ══════════════════════════════════════════════════

VEHICLES = {
    "hatchback": [
        "Maruti Alto hatchback clean body",
        "Hyundai i20 hatchback polished paint",
        "Maruti Swift hatchback sporty design",
        "Tata Tiago hatchback modern design",
        "Maruti Wagon R hatchback tall body",
        "Tata Punch hatchback SUV style",
    ],
    "sedan": [
        "Honda City sedan sleek profile",
        "Maruti Dzire sedan compact design",
        "Hyundai Verna sedan elegant design",
        "Honda Amaze sedan polished",
    ],
    "suv": [
        "Mahindra Scorpio SUV powerful stance",
        "Hyundai Creta SUV modern design",
        "Kia Seltos SUV polished paint",
        "Tata Nexon SUV bold design",
        "Toyota Fortuner large SUV",
        "Mahindra Bolero rugged SUV",
    ],
    "bikes_commuter": [
        "Hero Splendor commuter bike clean",
        "Bajaj Pulsar 150 sporty commuter",
        "Honda Shine commuter bike",
        "TVS Apache 160 sporty design",
    ],
    "bikes_royal_enfield": [
        "Royal Enfield Classic 350 vintage style",
        "Royal Enfield Bullet 350 iconic silhouette",
        "Royal Enfield Meteor 350 cruiser stance",
        "Royal Enfield Himalayan adventure bike",
    ],
    "bikes_sports": [
        "Bajaj Pulsar NS200 sporty aggressive stance",
        "Yamaha R15 racing fairing design",
        "KTM Duke 200 aggressive naked design",
    ],
    "scooter": [
        "Honda Activa scooter classic design",
        "TVS Jupiter scooter modern design",
        "Yamaha Fascino scooter stylish",
    ],
    "auto_rickshaw": [
        "Indian yellow auto rickshaw three-wheeler",
        "electric auto rickshaw modern design",
        "auto rickshaw front view showing windshield",
        "auto rickshaw rear view",
    ],
}

CAR_VIEWS = [
    "front view", "side profile view", "45 degree angle view",
    "rear three-quarter view", "low angle hero shot",
]

CAR_DETAILS = [
    "showroom quality clean bodywork",
    "polished automotive photography",
    "commercial vehicle photography",
    "studio automotive quality",
]

def gen_vehicles():
    items = []
    for sub, descs in VEHICLES.items():
        for desc, view, detail in iterproduct(descs, CAR_VIEWS, CAR_DETAILS[:2]):
            prompt = f"A {desc}, {view}, {detail}, {VEHICLE_BASE}"
            items.append(_item("vehicles", sub, prompt,
                               sub.replace("_", " ").title()))
    return dedup(items)

# ══════════════════════════════════════════════════
# SEED VARIATION SUFFIXES
# Adds variation to avoid duplicate outputs
# ══════════════════════════════════════════════════

_VARIATIONS = [
    "ultra sharp fine detail",
    "crisp clean commercial quality",
    "true to life color accuracy",
    "lifelike photographic detail",
    "fine surface texture detail",
    "studio grade photographic quality",
]

# ══════════════════════════════════════════════════
# PROMPT ENGINE CLASS (backward compatible)
# ══════════════════════════════════════════════════

class PromptEngine:
    """
    Unified Prompt Engine V2.0
    Generates FLUX-style natural language prompts for all 23 categories.
    """

    def generate_all_prompts(self):
        print("🎨 Guru Image Usha — Unified Prompt Engine V2.0")
        print("=" * 60)
        all_p = []

        generators = [
            ("Poultry & Animals",      gen_poultry_animals),
            ("Fish & Seafood",         gen_fish_seafood),
            ("Eggs",                   gen_eggs),
            ("Flowers",                gen_flowers),
            ("Fruits",                 gen_fruits),
            ("Vegetables",             gen_vegetables),
            ("Cool Drinks",            gen_drinks),
            ("Indian Foods",           gen_indian_food),
            ("World Foods",            gen_world_food),
            ("Dairy Products",         gen_dairy),
            ("Dry Fruits & Nuts",      gen_dry_fruits),
            ("Bakery & Snacks",        gen_bakery),
            ("Ayurvedic / Herbal",     gen_ayurveda),
            ("Indian Sweets",          gen_sweets),
            ("Stationery Groups",      gen_stationery),
            ("Kitchen Vessels",        gen_kitchen),
            ("Mobile Accessories",     gen_mobile),
            ("Computer Accessories",   gen_computer),
            ("Footwear",               gen_footwear),
            ("Indian Dress",           gen_dress),
            ("Jewellery Models",       gen_jewellery_models),
            ("Office Models",          gen_office_models),
            ("Vehicles",               gen_vehicles),
        ]

        counts = {}
        for name, fn in generators:
            prev = len(all_p)
            all_p.extend(fn())
            c = len(all_p) - prev
            counts[name] = c
            print(f"  ✅ {name}: {c}")

        # Seed multiplier ×2 — adds variation to each prompt
        extended = []
        for item in all_p:
            extended.append(item)
            copy = dict(item)
            var  = random.choice(_VARIATIONS)
            copy["prompt"] = item["prompt"].rstrip(", ") + f", {var}"
            copy["seed"]   = random.randint(100000, 999999)
            extended.append(copy)
        all_p = extended

        print(f"\n  🔁 Seed multiplier ×2: {len(all_p)} total prompts")
        random.shuffle(all_p)

        for i, item in enumerate(all_p):
            item["index"]    = i
            item["filename"] = f"img_{i:06d}.png"
            item["status"]   = "pending"

        print(f"\n🎯 TOTAL: {len(all_p)} prompts")
        print("\n📊 Summary (base × 2):")
        for name, c in counts.items():
            print(f"   {name:30s}: {c:5d} → {c*2:5d}")
        return all_p

    def save_prompts(self, output_dir="prompts/splits"):
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        prompts = self.generate_all_prompts()

        by_cat = {}
        for p in prompts:
            key = p.get("category", "misc").replace("/", "_")
            by_cat.setdefault(key, []).append(p)

        for cat, items in by_cat.items():
            fpath = out / f"{cat}.json"
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(items, f, indent=2, ensure_ascii=False)
            kb = fpath.stat().st_size / 1024
            print(f"  💾 {cat}.json → {len(items)} prompts ({kb:.0f} KB)")

        idx = {
            "total":      len(prompts),
            "categories": list(by_cat.keys()),
            "files":      [f"{c}.json" for c in by_cat],
        }
        with open(out / "index.json", "w", encoding="utf-8") as f:
            json.dump(idx, f, indent=2, ensure_ascii=False)

        print(f"\n✅ Saved {len(prompts)} prompts → {len(by_cat)} categories")
        return output_dir


# ══════════════════════════════════════════════════
# load_all_prompts — UNCHANGED INTERFACE
# Called by main_pipeline.py to load split JSONs
# ══════════════════════════════════════════════════

def load_all_prompts(splits_dir="prompts/splits"):
    """
    Load all prompt JSONs from the splits directory.
    Interface unchanged — main_pipeline.py imports this.
    """
    splits     = Path(splits_dir)
    index_file = splits / "index.json"

    if index_file.exists():
        idx   = json.loads(index_file.read_text())
        files = [splits / f for f in idx["files"]]
    else:
        files = [f for f in sorted(splits.glob("*.json"))
                 if f.name != "index.json"]

    all_p = []
    for fpath in files:
        try:
            with open(fpath, encoding="utf-8") as f:
                all_p.extend(json.load(f))
        except Exception as e:
            print(f"  Warning: Could not load {fpath.name}: {e}")

    print(f"📦 Loaded {len(all_p)} prompts from {len(files)} files.")
    return all_p


# ══════════════════════════════════════════════════
# MAIN — run to regenerate split JSONs
# ══════════════════════════════════════════════════

if __name__ == "__main__":
    PromptEngine().save_prompts("prompts/splits")
