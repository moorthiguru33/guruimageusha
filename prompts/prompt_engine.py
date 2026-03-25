"""
PNG Library — Prompt Engine V5 (GURU IMAGE USHA)
══════════════════════════════════════════════════════════
RULE  : Simple item names only. No confusing words.
BG    : SOLID LIGHT GREY — every single image
STYLE : 100% Ultra Realistic Studio Photography
══════════════════════════════════════════════════════════
Categories:
  1.  Poultry & Live Animals
  2.  Fish & Seafood
  3.  Eggs
  4.  Flowers
  5.  Fruits
  6.  Vegetables
  7.  Cool Drinks
  8.  Indian Foods
  9.  World Foods
  10. Dairy Products
  11. Dry Fruits & Nuts
  12. Bakery & Snacks
  13. Ayurvedic / Herbal
  14. Indian Sweets Shop
  15. School Stationery (20 groups)
  16. Kitchen Vessels (30 groups)
  17. Mobile Accessories (real brands)
  18. Computer & Accessories (real brands)
  19. Footwear
  20. Indian Dress
  21. Jewellery Models
  22. Office Models
  23. Vehicles
══════════════════════════════════════════════════════════
"""

import random
import json
from pathlib import Path

# ─────────────────────────────────────────────────────────────
# BASE SUFFIXES
# Grey background is repeated strongly so AI never generates black
# ─────────────────────────────────────────────────────────────

BASE_SUFFIX = (
    "isolated on solid plain light grey background, "
    "NOT black background, grey studio backdrop, "
    "professional studio product photography, "
    "Canon EOS R5 100mm macro lens, "
    "8k ultra high definition, ultra realistic, photorealistic, "
    "razor sharp focus, softbox studio lighting, "
    "clean crisp edges, centered composition"
)

ANIMAL_SUFFIX = (
    "isolated on solid plain light grey background, "
    "NOT black background, grey studio backdrop, "
    "professional studio animal photography, "
    "Canon EOS R5, 8k ultra high definition, ultra realistic, photorealistic, "
    "razor sharp focus, softbox lighting, "
    "clean crisp edges, centered full body"
)

MODEL_SUFFIX = (
    "isolated on solid plain light grey background, "
    "NOT black background, grey studio backdrop, "
    "professional studio fashion portrait photography, "
    "Canon EOS R5 85mm portrait lens, "
    "8k ultra high definition, ultra realistic, photorealistic, "
    "razor sharp focus, softbox studio lighting, "
    "clean crisp edges, centered composition"
)

# ─────────────────────────────────────────────────────────────
# VARIATION BANKS
# ─────────────────────────────────────────────────────────────

ANGLES = [
    "front view",
    "45 degree angle view",
    "top view overhead",
    "side profile view",
    "3/4 angle view",
    "close-up macro view",
    "low angle view",
    "eye level view",
]

LIGHTING = [
    "soft studio lighting",
    "bright even studio lighting",
    "high key studio lighting",
    "professional softbox lighting",
    "clean studio strobe lighting",
]

QUALITY = [
    "ultra fine detail",
    "sharp crisp quality",
    "lifelike realistic",
    "true to life detail",
    "every detail visible",
]

PHOTO = [
    "commercial product photography",
    "editorial photography",
    "studio catalog photography",
    "advertising photography",
]

# ─────────────────────────────────────────────────────────────
# 1. POULTRY & LIVE ANIMALS
# ─────────────────────────────────────────────────────────────

POULTRY_ANIMALS = {
    "rooster": [
        "single rooster standing side view",
        "single rooster front view",
        "single rooster crowing",
        "single rooster close-up head portrait",
        "single rooster full body 3/4 view",
        "single rooster tail feathers visible",
        "two roosters together",
        "three roosters group",
        "rooster and hen pair together",
    ],
    "broiler_chicken": [
        "single broiler chicken standing side view",
        "single broiler chicken front view",
        "single broiler chicken full body",
        "single broiler chicken close-up",
        "two broiler chickens together",
        "three broiler chickens group",
        "four broiler chickens together",
        "flock of broiler chickens",
    ],
    "goat": [
        "single goat standing side view",
        "single goat front view",
        "single goat full body",
        "single goat close-up head",
        "single young kid goat",
        "two goats together",
        "three goats group",
        "mother goat with baby kid",
    ],
    "quail": [
        "single quail bird standing",
        "single quail side view",
        "single quail front view",
        "single quail close-up",
        "two quail birds together",
        "three quail birds group",
        "five quail birds group",
    ],
    "cow": [
        "single Indian cow standing side view",
        "single cow front view",
        "single cow full body",
        "single cow close-up head",
        "single cow with hump visible",
        "two cows together",
        "cow with calf together",
        "three cows group",
    ],
}

ANIMAL_CONTEXTS = [
    "professional studio portrait",
    "clean full body view",
    "natural standing pose",
    "alert pose",
    "calm relaxed pose",
    "side profile full view",
]

# ─────────────────────────────────────────────────────────────
# 2. FISH & SEAFOOD
# ─────────────────────────────────────────────────────────────

FISH_SEAFOOD = {
    "whole_fish": [
        # Single
        "single Rohu fish whole",
        "single Catla fish whole",
        "single Pomfret fish whole",
        "single Seer fish Vanjaram whole",
        "single Mackerel Ayala fish whole",
        "single Sardine Mathi fish whole",
        "single Tilapia fish whole",
        "single Salmon fish whole",
        "single Red Snapper fish whole",
        "single Tuna fish whole",
        "single Barramundi fish whole",
        "single King fish whole",
        "single Hilsa fish whole",
        "single Catfish whole",
        "single Sole fish whole",
        # Group
        "two Pomfret fish arranged together",
        "three Sardines arranged together",
        "three Mackerel fish arranged together",
        "pile of small fish arranged",
        "two Rohu fish together",
        "fish on banana leaf arranged",
        "fish on steel tray arranged",
        "four small fish in a row",
        "fish market style arrangement three fish",
        "mixed fish variety arranged together",
    ],
    "prawns_shrimp": [
        # Single
        "single large prawn whole",
        "single tiger prawn whole",
        "single king prawn whole",
        # Group
        "three prawns arranged together",
        "pile of fresh prawns",
        "prawns on banana leaf",
        "six prawns arranged in a row",
        "prawns in bowl arranged",
        "mixed prawns pile fresh",
        "tiger prawns four arranged",
        "prawns on plate arranged",
    ],
    "crab": [
        "single whole crab front view",
        "single crab side view",
        "single mud crab whole",
        "two crabs arranged together",
        "three crabs group arranged",
        "crab on banana leaf",
        "crab on plate arranged",
        "crabs pile together",
    ],
    "squid_other": [
        "single squid whole",
        "squid on plate arranged",
        "two squid together",
        "pile of squid fresh",
        "single lobster whole",
        "lobster on plate",
        "single oyster shell open",
        "mussels cluster arranged",
        "mixed seafood arranged on plate",
        "seafood variety platter arranged",
    ],
}

FISH_CONTEXTS = [
    "on white surface",
    "on banana leaf",
    "on white plate",
    "on steel tray",
    "on dark slate board",
    "top view overhead",
    "side view",
    "close-up detail",
]

FISH_STYLE = [
    "fresh seafood photography",
    "food market photography",
    "commercial seafood photography",
    "studio food photography",
]

# ─────────────────────────────────────────────────────────────
# 3. EGGS
# ─────────────────────────────────────────────────────────────

EGGS = [
    "single egg on white surface",
    "single egg top view",
    "single egg close-up",
    "cracked egg with yolk",
    "three eggs arranged together",
    "six eggs arranged in two rows",
    "dozen eggs in carton",
    "eggs in wicker basket",
    "pile of eggs together",
    "four eggs on grey surface",
    "eggs in white bowl",
    "quail eggs small cluster",
    "six quail eggs arranged",
    "two types eggs together",
    "eggs on wooden surface natural",
]

EGG_CONTEXTS = [
    "on white surface",
    "on wooden surface",
    "in basket",
    "top view overhead",
    "close-up detail",
    "on grey surface",
]

# ─────────────────────────────────────────────────────────────
# 4. FLOWERS
# ─────────────────────────────────────────────────────────────

FLOWERS_SINGLE = {
    "rose": [
        "single red rose",
        "single pink rose",
        "single white rose",
        "single yellow rose",
        "single orange rose",
        "red rose bud",
        "rose with green leaves",
        "rose top view",
        "rose close-up petals",
        "rose side view",
    ],
    "lotus": [
        "single pink lotus open",
        "single white lotus open",
        "lotus bud",
        "lotus top view",
        "lotus side view",
        "lotus with green leaf",
    ],
    "jasmine": [
        "jasmine flower cluster white",
        "jasmine bunch fresh",
        "jasmine close-up",
        "jasmine on stem",
        "jasmine garland",
        "jasmine top view",
    ],
    "marigold": [
        "single orange marigold",
        "single yellow marigold",
        "marigold top view",
        "marigold close-up",
        "marigold bunch tied",
        "marigold side view",
    ],
    "sunflower": [
        "single sunflower front view",
        "sunflower side view",
        "sunflower close-up center",
        "sunflower with stem",
        "sunflower top view",
        "sunflower bud",
    ],
    "hibiscus": [
        "single red hibiscus open",
        "single yellow hibiscus",
        "single pink hibiscus",
        "hibiscus close-up",
        "hibiscus side view",
        "hibiscus top view",
    ],
    "lily": [
        "single white lily",
        "single pink lily",
        "lily close-up",
        "lily side view",
        "lily with stem",
        "lily top view",
    ],
    "orchid": [
        "single purple orchid",
        "single white orchid",
        "single pink orchid",
        "orchid close-up",
        "orchid on stem",
        "orchid side view",
    ],
}

FLOWERS_GROUP = [
    "bunch of red roses arranged",
    "mixed flower bouquet colorful",
    "three roses together",
    "five roses bouquet",
    "marigold bunch tied together",
    "jasmine and rose mixed bunch",
    "flowers in small glass vase",
    "flower arrangement flat lay",
    "three sunflowers together",
    "lotus flowers two together",
    "hibiscus flowers three arranged",
    "lily bunch together",
    "orchid spray on stem",
    "mixed Indian flowers bunch",
    "wedding flower bouquet white",
    "festival flowers colorful bunch",
    "flower basket overflowing",
    "dozen roses bouquet",
    "temple flowers marigold jasmine",
    "fresh flowers flat lay overhead",
    "colorful mixed flowers arranged",
    "rose and jasmine garland",
    "bridal flower arrangement",
    "flowers in ceramic vase",
    "wildflower mixed bunch natural",
]

FLOWER_CONTEXTS = [
    "close-up",
    "with dew drops on petals",
    "with green leaves",
    "in full bloom",
    "top view",
    "side view",
]

FLOWER_PHOTO = [
    "macro floral photography",
    "botanical studio photography",
    "fine art floral photography",
    "natural light photography",
]

# ─────────────────────────────────────────────────────────────
# 5. FRUITS
# ─────────────────────────────────────────────────────────────

FRUITS_SINGLE = {
    "mango":         ["single mango whole", "mango cut in half", "mango sliced", "mango top view", "mango close-up", "mango with leaf"],
    "banana":        ["single banana", "single banana peeled", "green banana", "banana top view", "banana close-up"],
    "apple":         ["single apple whole", "apple cut in half", "apple slice", "apple top view", "apple with stem"],
    "watermelon":    ["whole watermelon", "watermelon slice", "watermelon half", "watermelon cubes", "watermelon top view"],
    "grapes":        ["bunch of grapes", "grapes close-up", "green grapes bunch", "grapes top view"],
    "orange":        ["single orange whole", "orange cut in half", "orange slice round", "orange top view", "orange close-up"],
    "lemon":         ["single lemon whole", "lemon cut in half", "lemon slice", "lemon top view", "lemon with leaf"],
    "coconut":       ["green tender coconut whole", "coconut with straw", "coconut cut open", "mature coconut whole", "coconut top view"],
    "papaya":        ["whole papaya", "papaya cut in half", "papaya sliced", "papaya top view", "papaya close-up"],
    "pomegranate":   ["whole pomegranate", "pomegranate cut in half", "pomegranate seeds", "pomegranate top view"],
    "pineapple":     ["whole pineapple", "pineapple slice", "pineapple cut in half", "pineapple top view"],
    "guava":         ["single guava whole", "guava cut in half", "guava slice", "guava top view", "guava close-up"],
    "other_fruits":  [
        "single strawberry", "kiwi cut in half", "dragon fruit cut in half",
        "fig cut in half", "chikoo whole", "jackfruit piece",
        "custard apple whole", "plum whole", "peach whole", "cherry pair with stem",
    ],
}

FRUITS_GROUP = [
    "3 mangoes arranged together",
    "mango pile heap together",
    "2 mangoes one cut open",
    "single banana on surface",
    "bunch of 6 bananas",
    "2 bananas together",
    "3 apples arranged",
    "4 apples grouped",
    "2 oranges one sliced",
    "3 oranges arranged",
    "3 lemons arranged",
    "2 lemons together",
    "watermelon with slice beside",
    "3 guavas arranged",
    "grapes and apples together",
    "mixed fruit basket",
    "all fruits flat lay collection",
    "tropical fruits arranged",
    "Indian fruits variety together",
    "fruit platter cut fruits",
    "4 pomegranates arranged",
    "3 papayas together",
    "3 coconuts arranged",
    "mixed citrus fruits together",
    "strawberries pile",
    "kiwi and strawberry arranged",
    "fruit market style mixed",
    "seasonal fruits collection",
    "two pineapples arranged",
    "mixed berries cluster together",
]

FRUIT_CONTEXTS = [
    "on white surface",
    "on wooden surface",
    "top view overhead",
    "close-up",
    "with water droplets",
    "with leaves attached",
]

# ─────────────────────────────────────────────────────────────
# 6. VEGETABLES
# ─────────────────────────────────────────────────────────────

VEGS_SINGLE = {
    "tomato":       ["single tomato whole", "tomato cut in half", "tomato top view", "tomato close-up", "tomato with stem", "tomato slice"],
    "potato":       ["single potato whole", "potato cut in half", "potato top view", "potato close-up", "baby potato whole"],
    "sweet_potato": ["single sweet potato whole", "sweet potato cut in half", "sweet potato top view", "sweet potato close-up"],
    "brinjal":      ["single brinjal whole", "brinjal cut in half", "brinjal top view", "brinjal close-up", "long brinjal whole", "round brinjal whole"],
    "onion":        ["single onion whole", "onion cut in half", "onion top view", "onion slice rings", "small shallots cluster", "spring onion bunch"],
    "carrot":       ["single carrot whole", "carrot cut in half", "carrot slice rounds", "carrot top view", "baby carrots bunch"],
    "capsicum":     ["single green capsicum", "single red capsicum", "single yellow capsicum", "capsicum cut in half", "capsicum top view"],
    "okra":         ["single okra whole", "okra bunch fresh", "okra cut open", "okra top view", "okra flat lay"],
    "cucumber":     ["single cucumber whole", "cucumber slice rounds", "cucumber cut in half", "cucumber top view", "cucumber close-up"],
    "beans":        ["green beans bunch", "beans flat lay", "beans top view", "beans close-up"],
    "other_veggies": [
        "cauliflower whole", "broccoli whole", "cabbage whole",
        "bitter gourd whole", "drumstick whole", "ginger root",
        "garlic bulb whole", "spinach bunch", "pumpkin whole",
        "pumpkin cut in half",
    ],
}

VEGS_GROUP = [
    "3 tomatoes arranged",
    "4 tomatoes grouped",
    "tomatoes in bowl",
    "3 brinjals arranged",
    "4 brinjals grouped",
    "3 potatoes arranged",
    "potatoes in jute bag",
    "potatoes in basket",
    "pile of potatoes",
    "4 sweet potatoes arranged",
    "sweet potatoes in basket",
    "3 onions arranged",
    "pile of onions",
    "onions in jute bag",
    "3 carrots arranged",
    "carrot bunch tied",
    "3 cucumbers arranged",
    "3 capsicums mixed colors together",
    "okra bunch arranged",
    "beans pile arranged",
    "mixed vegetables flat lay",
    "Indian cooking vegetables arranged",
    "vegetable basket overflowing",
    "vegetables in jute bag",
    "mixed vegetables market style",
    "cauliflower and broccoli together",
    "garlic onion ginger together",
    "mixed green vegetables bunch",
    "vegetable platter variety",
    "all vegetables flat lay collection",
]

VEG_CONTEXTS = [
    "on white surface",
    "on wooden surface",
    "top view overhead",
    "close-up",
    "with water droplets",
    "with stem attached",
]

# ─────────────────────────────────────────────────────────────
# 7. COOL DRINKS
# ─────────────────────────────────────────────────────────────

COOL_DRINKS = {
    "mojito":         ["mojito in tall glass with mint and lime", "mint mojito with crushed ice", "mojito with straw and lime slice", "mojito in mason jar", "mojito top view", "two mojito glasses together", "strawberry mojito in glass", "mango mojito in glass"],
    "lemon_soda":     ["lemon soda in glass with ice", "nimbu pani in glass", "lemon soda with lemon slice", "fresh lime soda fizzy", "masala lemon soda in glass", "lemon soda top view", "two lemon sodas together", "lemon soda in clay kulhad"],
    "lassi":          ["mango lassi in tall glass", "plain lassi in brass glass", "sweet lassi frothy", "lassi with cream on top", "lassi in clay kulhad", "lassi top view", "two lassi glasses", "rose lassi in glass", "lassi close-up frothy"],
    "tender_coconut": ["tender coconut with straw", "green coconut with straw", "tender coconut cut open", "tender coconut top view", "two tender coconuts together", "three coconuts arranged", "coconut water in glass with coconut beside"],
    "fresh_juice":    ["orange juice in glass with orange slice", "sugarcane juice in glass", "watermelon juice in glass", "pomegranate juice in glass", "carrot juice in glass", "mixed fruit juice in glass", "juice glass top view", "two juice glasses together"],
    "buttermilk":     ["buttermilk in glass", "buttermilk in brass tumbler", "buttermilk in clay pot", "buttermilk with curry leaves", "buttermilk frothy in glass", "buttermilk top view", "two buttermilk glasses", "masala buttermilk in glass"],
}

DRINK_VESSELS = [
    "in tall clear glass",
    "in brass tumbler",
    "in clay kulhad",
    "in mason jar",
    "in ceramic glass",
]

DRINK_DETAILS = [
    "condensation on glass",
    "with garnish on top",
    "with straw",
    "ice cubes visible",
    "frothy top",
]

# ─────────────────────────────────────────────────────────────
# 8. INDIAN FOODS
# ─────────────────────────────────────────────────────────────

INDIAN_FOODS = {
    "biryani":    ["biryani in bowl", "biryani on banana leaf", "biryani in clay pot", "biryani top view", "chicken biryani in bowl", "mutton biryani on plate", "biryani with raita", "biryani steam rising", "biryani close-up", "biryani on steel thali"],
    "dosa":       ["masala dosa on plate with chutneys", "dosa on banana leaf", "crispy dosa with sambar", "dosa top view", "set dosa stack on plate", "egg dosa on plate", "dosa folded on plate", "paper dosa on plate", "dosa close-up texture"],
    "idly":       ["idly on plate with sambar", "idly on banana leaf", "idly stack on plate", "idly top view", "mini idly on plate", "idly with coconut chutney", "four idly on steel plate", "idly with podi powder", "idly close-up texture"],
    "parotta":    ["parotta on plate layered", "parotta on banana leaf", "parotta close-up layers", "parotta top view", "two parotta on plate", "parotta with salna", "kothu parotta on plate", "parotta stack layers visible"],
    "curry":      ["chicken curry in bowl", "mutton curry in clay pot", "fish curry in bowl", "egg curry in bowl", "prawn curry in bowl", "crab curry on plate", "curry with rice on plate", "curry on banana leaf", "thick curry in steel bowl"],
    "rice":       ["lemon rice on banana leaf", "curd rice in bowl", "tomato rice on plate", "plain rice with ghee", "pongal in bowl", "sambar rice on plate", "ghee rice in bowl", "coconut rice on banana leaf", "tamarind rice on plate"],
    "snacks":     ["samosa on plate", "medu vada on plate", "murukku on plate", "pakora on plate", "bajji on plate", "banana chips on plate", "masala vada on plate", "bread pakora on plate", "snacks platter arranged"],
}

INDIAN_VESSELS = [
    "on banana leaf", "in steel thali", "in ceramic bowl",
    "in clay pot", "on white plate", "in copper bowl",
]

# ─────────────────────────────────────────────────────────────
# 9. WORLD FOODS
# ─────────────────────────────────────────────────────────────

WORLD_FOODS = {
    "pizza":         ["whole pizza on wooden board", "pizza slice", "pizza top view", "pizza close-up cheese", "pizza side view", "two pizza slices", "mini pizza", "pizza fresh from oven"],
    "burger":        ["burger whole on plate", "burger cut in half showing layers", "burger side view", "burger top view", "burger with fries", "double burger", "burger close-up", "two burgers arranged"],
    "fried_chicken": ["fried chicken piece on plate", "fried chicken drumstick", "fried chicken bucket", "fried chicken strips", "fried chicken close-up crispy", "fried chicken top view", "four fried chicken pieces", "fried chicken with sauce"],
    "french_fries":  ["french fries in box", "french fries in cone", "french fries on plate", "french fries close-up", "french fries top view", "large fries in box", "fries with sauce", "waffle fries on plate"],
    "noodles":       ["noodles in bowl", "noodles top view", "noodles close-up", "ramen bowl with egg", "stir fried noodles in bowl", "noodles with vegetables", "noodle bowl steam rising", "noodles with chopsticks"],
    "fried_rice":    ["fried rice in bowl", "fried rice on plate", "fried rice top view", "fried rice close-up", "fried rice in wok", "fried rice with egg", "fried rice with vegetables", "fried rice with chopsticks"],
    "chinese":       ["spring rolls on plate", "dim sum in bamboo basket", "chicken manchurian in bowl", "gobi manchurian on plate", "wonton soup in bowl", "spring rolls close-up", "dim sum top view", "chinese food platter"],
}

WORLD_VESSELS = [
    "on white plate", "on wooden board", "in ceramic bowl",
    "on slate board", "in paper box", "in bamboo basket",
]

FOOD_ANGLES = [
    "overhead flat lay", "45 degree angle", "front view", "close-up macro", "side view",
]

# ─────────────────────────────────────────────────────────────
# 10. DAIRY PRODUCTS
# ─────────────────────────────────────────────────────────────

DAIRY = {
    "milk": [
        "glass of milk full",
        "milk in glass top view",
        "milk pouring into glass",
        "two glasses of milk",
        "milk bottle sealed",
        "milk packet sealed",
        "milk close-up in glass",
        "milk jug full",
        "milk in steel glass",
    ],
    "curd_yogurt": [
        "curd in clay pot",
        "curd in white bowl",
        "curd top view in bowl",
        "yogurt in glass jar",
        "curd close-up texture",
        "curd with tempering on top",
        "curd in steel bowl",
        "two bowls of curd",
        "curd in ceramic bowl",
    ],
    "butter_ghee": [
        "butter block on white plate",
        "butter close-up texture",
        "butter on wooden board",
        "ghee in glass jar",
        "ghee in steel container",
        "ghee jar top view",
        "butter and ghee together",
        "butter slice on plate",
        "ghee close-up golden",
    ],
    "paneer": [
        "paneer block whole",
        "paneer cubes arranged on plate",
        "paneer cut in half",
        "paneer close-up texture",
        "paneer top view",
        "paneer slice on plate",
        "three paneer blocks arranged",
        "paneer in bowl",
        "fresh paneer on banana leaf",
    ],
    "cheese": [
        "cheese block whole",
        "cheese slice on plate",
        "cheese cubes arranged",
        "cheese close-up texture",
        "cheese top view",
        "two cheese blocks together",
        "cheese on wooden board",
        "mozzarella cheese ball",
        "cheese spread in bowl",
    ],
}

DAIRY_CONTEXTS = [
    "on white surface", "on wooden surface",
    "top view", "close-up", "side view",
]

# ─────────────────────────────────────────────────────────────
# 11. DRY FRUITS & NUTS
# ─────────────────────────────────────────────────────────────

DRY_FRUITS = {
    "single": [
        "cashew nuts on white plate",
        "almonds on white plate",
        "pistachios on white plate",
        "walnuts on white plate",
        "raisins on white plate",
        "dates on white plate",
        "figs dried on plate",
        "apricots dried on plate",
        "peanuts on white plate",
        "pine nuts on white plate",
        "hazelnuts on white plate",
        "macadamia nuts on plate",
        "pecan nuts on plate",
        "brazil nuts on plate",
        "sunflower seeds on plate",
    ],
    "group": [
        "cashews pile on plate",
        "almonds pile arranged",
        "mixed dry fruits on plate",
        "mixed nuts variety bowl",
        "dry fruits in small bowls arranged",
        "cashew almond pistachio together",
        "dry fruits flat lay collection",
        "nuts and seeds mixed bowl",
        "dry fruits in glass jar",
        "dry fruits platter arranged",
        "three bowls nuts arranged",
        "dry fruits gift box arranged",
        "all nuts variety flat lay",
        "dry fruits on wooden board",
        "assorted dry fruits collection",
    ],
}

DRY_FRUIT_CONTEXTS = [
    "on white plate", "in small wooden bowl", "in glass bowl",
    "top view overhead", "close-up", "scattered on surface",
]

# ─────────────────────────────────────────────────────────────
# 12. BAKERY & SNACKS
# ─────────────────────────────────────────────────────────────

BAKERY = {
    "bread": [
        "bread loaf whole",
        "bread slices arranged",
        "bread cut in half",
        "bread top view",
        "bread close-up texture",
        "two bread slices",
        "bread on wooden board",
        "whole grain bread loaf",
        "pav bread rolls arranged",
        "bun bread single",
    ],
    "cake": [
        "whole round cake with frosting",
        "cake slice on plate",
        "chocolate cake whole",
        "birthday cake with candles",
        "cake top view",
        "two cake slices arranged",
        "cake on wooden board",
        "cupcake single",
        "three cupcakes arranged",
        "cake close-up frosting",
    ],
    "biscuits_cookies": [
        "biscuits pile on plate",
        "cookies arranged on plate",
        "biscuits in glass jar",
        "cookies top view",
        "biscuits close-up texture",
        "three cookies arranged",
        "Parle G biscuit packet",
        "bourbon biscuit arranged",
        "digestive biscuits on plate",
        "cookies on wooden board",
    ],
    "snacks": [
        "potato chips in bowl",
        "Lays chips packet",
        "Kurkure snack packet",
        "Haldiram snacks packet",
        "popcorn in bowl",
        "popcorn top view",
        "chips pile in bowl",
        "mixed snacks bowl",
        "nachos in bowl",
        "puffed rice snack bowl",
    ],
}

BAKERY_CONTEXTS = [
    "on white surface", "on wooden board",
    "top view", "close-up", "on plate",
]

# ─────────────────────────────────────────────────────────────
# 13. AYURVEDIC / HERBAL
# ─────────────────────────────────────────────────────────────

AYURVEDA = {
    "plants_leaves": [
        "neem leaves bunch fresh",
        "tulsi holy basil plant",
        "aloe vera plant whole",
        "aloe vera leaf close-up",
        "curry leaves bunch fresh",
        "mint leaves fresh bunch",
        "lemongrass stalks fresh",
        "moringa drumstick leaves",
        "ashwagandha root dried",
        "brahmi leaves fresh",
    ],
    "herbs_roots": [
        "turmeric root fresh",
        "turmeric powder in bowl",
        "ginger root fresh",
        "dry ginger piece",
        "cinnamon sticks bundle",
        "black pepper whole pile",
        "cardamom pods green pile",
        "cloves whole pile",
        "star anise whole",
        "fenugreek seeds in bowl",
    ],
    "products": [
        "ayurvedic oil bottle",
        "herbal powder in bowl",
        "herbal tablets arranged",
        "neem powder in bowl",
        "herbal tea in glass",
        "ayurvedic churna in bowl",
        "mortar and pestle with herbs",
        "herbal oil in glass bottle",
        "natural soap herbal",
        "ayurvedic capsules arranged",
    ],
    "group": [
        "turmeric ginger neem together",
        "ayurvedic herbs flat lay collection",
        "herbal roots arranged on surface",
        "three ayurvedic bottles arranged",
        "mixed herbs and spices arranged",
        "ayurvedic ingredients flat lay",
        "herbs in small bowls arranged",
        "natural remedies collection",
        "five herbal ingredients arranged",
        "ayurvedic product set arranged",
    ],
}

AYUR_CONTEXTS = [
    "on white surface", "on wooden surface",
    "top view", "close-up", "in small bowl",
]

# ─────────────────────────────────────────────────────────────
# 14. INDIAN SWEETS SHOP
# ─────────────────────────────────────────────────────────────

INDIAN_SWEETS = {
    "single": [
        "mysore pak on plate",
        "gulab jamun in bowl with syrup",
        "jalebi on plate",
        "halwa in bowl",
        "gajar halwa in bowl",
        "ladoo on plate",
        "kaju katli on plate",
        "barfi on plate",
        "rasgulla in bowl",
        "sandesh on plate",
        "peda on plate",
        "kheer in bowl",
        "payasam in bowl",
        "rava kesari in bowl",
        "coconut burfi on plate",
        "milk cake on plate",
        "balushahi on plate",
        "malpua on plate",
        "modak on plate",
        "puran poli on plate",
    ],
    "group": [
        "three mysore pak pieces on plate",
        "four gulab jamun in bowl",
        "jalebi pile on plate",
        "five ladoo arranged on plate",
        "kaju katli pieces arranged on plate",
        "mixed sweets platter arranged",
        "sweet shop display variety",
        "assorted Indian sweets on plate",
        "sweets box open with variety",
        "ten sweets variety flat lay",
        "three types barfi arranged",
        "sweets on banana leaf arranged",
        "festival sweets collection plate",
        "Indian mithai box open",
        "sweets on silver plate arranged",
        "diwali sweets variety platter",
        "six peda arranged on plate",
        "mixed halwa bowls three together",
        "sweets in traditional box",
        "grand sweets platter full variety",
    ],
}

SWEET_CONTEXTS = [
    "on white plate", "in silver plate", "on banana leaf",
    "in ceramic bowl", "top view", "close-up",
]

# ─────────────────────────────────────────────────────────────
# 15. SCHOOL STATIONERY — 20 GROUP PHOTOS ONLY
# ─────────────────────────────────────────────────────────────

STATIONERY_GROUPS = [
    "pencils and eraser and sharpener arranged together",
    "notebooks and pens arranged flat lay",
    "school bag with books and pencil box",
    "ruler scale compass and protractor together",
    "color pencils set arranged fan shape",
    "pen pencil ruler eraser flat lay",
    "geometry box open with instruments",
    "crayons set arranged colorful",
    "watercolor paint set with brushes",
    "marker pens set arranged colorful",
    "school books stack arranged",
    "pencil box open with stationery inside",
    "scissors glue tape and stapler together",
    "highlighter pens set arranged",
    "drawing book and sketching pencils together",
    "all stationery items flat lay collection",
    "backpack school bag open with items",
    "chalk pieces and blackboard duster together",
    "clipboard with paper and pen",
    "stationery items in pencil stand arranged",
]

# ─────────────────────────────────────────────────────────────
# 16. KITCHEN VESSELS — 30 GROUP COMBINATIONS ONLY
# ─────────────────────────────────────────────────────────────

KITCHEN_GROUPS = [
    "steel kadai and spatula together",
    "pressure cooker and steel vessel together",
    "three steel vessels stacked together",
    "clay pot and steel pot together",
    "steel thali and bowls set arranged",
    "cooking pots and pans set arranged",
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
    "steel cookware set arranged flat lay",
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

# ─────────────────────────────────────────────────────────────
# 17. MOBILE ACCESSORIES — REAL BRANDS ONLY
# ─────────────────────────────────────────────────────────────

MOBILE_ACCESSORIES = {
    "smartphones": [
        "iPhone 15 Pro front view",
        "iPhone 15 Pro side view",
        "iPhone 15 Pro top view",
        "Samsung Galaxy S24 Ultra front view",
        "Samsung Galaxy S24 Ultra side view",
        "OnePlus 12 front view",
        "OnePlus 12 side view",
        "Realme 12 Pro front view",
        "Realme 12 Pro side view",
        "Redmi Note 13 Pro front view",
        "Redmi Note 13 Pro side view",
        "Vivo V30 Pro front view",
        "OPPO Reno 11 front view",
        "Nothing Phone 2 front view",
        "Nothing Phone 2 side view",
        "Google Pixel 8 front view",
        "Google Pixel 8 side view",
    ],
    "earphones": [
        "Apple AirPods Pro in case",
        "Apple AirPods Pro top view",
        "Samsung Galaxy Buds in case",
        "OnePlus Buds in case",
        "Sony WF-1000XM5 earbuds in case",
        "Boat Airdopes earbuds in case",
        "Noise earbuds in case",
        "JBL wireless earbuds in case",
        "Realme Buds in case",
        "Redmi Buds in case",
        "earbuds case open top view",
        "two earbuds and case arranged",
    ],
    "chargers_cables": [
        "Apple 20W USB-C charger adapter",
        "Samsung 45W charger adapter",
        "USB-C charging cable coiled",
        "iPhone Lightning cable coiled",
        "wireless charger pad flat",
        "MagSafe charger Apple",
        "Anker charger adapter",
        "two chargers arranged together",
        "charging cable flat lay",
        "multi port USB hub",
    ],
    "phone_cases": [
        "iPhone clear case front view",
        "Samsung phone case front view",
        "phone cover on white surface",
        "three phone cases arranged",
        "phone case top view",
        "silicone phone case",
        "leather phone case",
        "phone case back view",
    ],
    "powerbanks": [
        "Anker power bank front view",
        "Mi power bank 20000mAh",
        "Samsung power bank front view",
        "power bank top view",
        "power bank with cable connected",
        "two power banks arranged",
        "Boat power bank front view",
        "power bank side view",
    ],
    "group": [
        "iPhone 15 Pro with AirPods Pro together",
        "Samsung phone with Samsung buds together",
        "smartphone charger and cable together",
        "phone case power bank earbuds arranged",
        "mobile accessories flat lay collection",
        "three smartphones arranged together",
        "earbuds charger and cable flat lay",
        "phone accessories full set arranged",
        "two phones side by side",
        "mobile setup flat lay complete",
    ],
}

MOBILE_CONTEXTS = [
    "on white surface", "on grey surface",
    "top view flat lay", "45 degree angle", "close-up",
]

# ─────────────────────────────────────────────────────────────
# 18. COMPUTER & ACCESSORIES — REAL BRANDS ONLY
# ─────────────────────────────────────────────────────────────

COMPUTER_ACCESSORIES = {
    "laptops": [
        "MacBook Air M2 open front view",
        "MacBook Pro 14 open side view",
        "MacBook Air top view flat lay",
        "Dell XPS 13 open front view",
        "Dell XPS 15 side view open",
        "HP Spectre x360 open front",
        "HP Pavilion laptop open front",
        "Lenovo ThinkPad open front view",
        "Lenovo IdeaPad open front view",
        "ASUS ZenBook open front view",
        "ASUS ROG gaming laptop open",
        "Acer Swift laptop open front",
        "laptop closed side profile",
        "laptop top view flat lay",
        "two laptops arranged together",
    ],
    "keyboards_mouse": [
        "Apple Magic Keyboard top view",
        "Apple Magic Mouse side view",
        "Apple keyboard and mouse together",
        "Logitech MX Keys keyboard",
        "Logitech MX Master mouse",
        "Logitech keyboard and mouse set",
        "mechanical keyboard top view",
        "wireless keyboard top view flat lay",
        "gaming keyboard RGB top view",
        "mouse close-up top view",
        "keyboard and mouse flat lay",
        "three keyboards arranged",
    ],
    "monitors": [
        "Dell monitor front view",
        "LG UltraWide monitor front view",
        "Samsung curved monitor front view",
        "Apple Studio Display front view",
        "monitor side profile view",
        "monitor top view",
        "two monitors arranged",
        "gaming monitor front view",
        "monitor close-up",
        "monitor with stand side view",
    ],
    "headphones": [
        "Sony WH-1000XM5 headphones",
        "Apple AirPods Max over-ear",
        "Bose QuietComfort headphones",
        "JBL over-ear headphones",
        "headphones top view",
        "headphones side view",
        "headphones flat lay",
        "two headphones arranged",
        "headphones close-up detail",
        "Sennheiser headphones front view",
    ],
    "other_accessories": [
        "USB-C hub multiport adapter",
        "external SSD Samsung T7",
        "external hard drive Western Digital",
        "webcam Logitech C920",
        "mouse pad desk mat",
        "laptop stand vertical",
        "USB hub on desk",
        "HDMI cable coiled",
        "external SSD top view",
        "laptop accessories flat lay",
    ],
    "group": [
        "MacBook with Apple keyboard and mouse arranged",
        "laptop keyboard mouse and headphones flat lay",
        "computer accessories complete desk setup flat lay",
        "monitor keyboard and mouse arranged",
        "two laptops with accessories arranged",
        "gaming setup monitor keyboard mouse headphones",
        "laptop accessories collection flat lay",
        "keyboard mouse and USB hub together",
        "laptop and external SSD together",
        "full computer desk setup aerial view",
    ],
}

COMPUTER_CONTEXTS = [
    "on white surface", "flat lay top view",
    "45 degree angle", "front view", "close-up detail",
]

# ─────────────────────────────────────────────────────────────
# 19. FOOTWEAR
# ─────────────────────────────────────────────────────────────

FOOTWEAR = {
    "chappals": [
        "single chappal side view", "pair of chappals front view",
        "chappals top view flat lay", "leather chappal close-up",
        "rubber chappal pair", "traditional chappal side view",
        "two chappals arranged", "chappal sole view",
    ],
    "sandals": [
        "single sandal side view", "pair of sandals front view",
        "sandals top view flat lay", "leather sandal close-up",
        "strappy sandal pair", "sandal 45 degree angle",
        "ladies sandal pair", "two sandals arranged",
    ],
    "shoes": [
        "single shoe side view", "pair of shoes front view",
        "shoes top view flat lay", "leather shoe close-up",
        "formal shoes pair", "shoe sole view",
        "shoes side by side", "shoe lace close-up",
    ],
    "heels": [
        "single heel shoe side view", "pair of heels front view",
        "heels top view flat lay", "stiletto heel close-up",
        "block heel shoe pair", "heels sole view",
        "ladies heels arranged", "pointed heel side view",
    ],
    "sports_shoes": [
        "single sports shoe side view", "pair of sports shoes front view",
        "sports shoes top view flat lay", "running shoes pair",
        "sports shoe sole detail", "sneakers side by side",
        "sports shoes 45 degree", "running shoes close-up",
    ],
    "kids": [
        "kids school shoes pair", "children sneakers front view",
        "kids sandal pair", "baby shoes tiny pair",
        "kids shoes top view flat lay", "children shoes side view",
    ],
}

SHOE_VIEWS = [
    "side profile view", "front view", "top view flat lay",
    "45 degree angle", "sole view", "close-up detail",
]

# ─────────────────────────────────────────────────────────────
# 20. INDIAN DRESS
# ─────────────────────────────────────────────────────────────

INDIAN_DRESS = {
    "saree": [
        "saree neatly folded", "saree draped showing fabric",
        "saree flat lay", "silk saree folded with border",
        "saree embroidery close-up", "bridal saree folded",
        "Kanchipuram saree folded", "Banarasi saree folded",
        "cotton saree folded", "saree zari border close-up",
    ],
    "salwar_kameez": [
        "salwar kameez set flat lay", "salwar suit folded",
        "anarkali suit flat lay", "salwar kameez embroidery close-up",
        "palazzo suit flat lay", "salwar kameez on hanger",
        "printed salwar kameez flat lay", "salwar kameez top view",
    ],
    "lehenga": [
        "lehenga skirt flat lay", "bridal lehenga folded",
        "lehenga embroidery close-up", "lehenga choli set flat lay",
        "lehenga fabric detail", "lehenga top view",
    ],
    "kurta": [
        "mens kurta folded flat lay", "kurta on hanger",
        "embroidered kurta flat lay", "silk kurta folded",
        "kurta pajama set arranged", "sherwani flat lay",
        "printed kurta flat lay", "plain white kurta folded",
    ],
    "kids_dress": [
        "kids lehenga choli flat lay", "kids kurta pajama flat lay",
        "baby girl frock flat lay", "boys sherwani flat lay",
        "girls salwar kameez flat lay", "kids ethnic wear flat lay",
        "children festive wear flat lay", "kids traditional dress",
    ],
}

DRESS_CONTEXTS = [
    "neatly folded on surface", "flat lay top view",
    "hanging full length", "embroidery detail close-up",
    "fabric texture close-up", "draped showing fabric",
]

# ─────────────────────────────────────────────────────────────
# 21. JEWELLERY MODELS
# ─────────────────────────────────────────────────────────────

JEWELLERY_MODELS = {
    "necklace": [
        "Indian woman wearing gold necklace portrait",
        "South Indian woman gold necklace portrait",
        "woman with gold necklace in saree portrait",
        "woman wearing layered gold necklace portrait",
        "woman gold necklace side profile portrait",
        "woman gold temple necklace portrait",
        "woman gold chain necklace portrait",
        "woman gold necklace smiling portrait",
        "woman wearing heavy gold necklace portrait",
        "bridal gold necklace model portrait",
    ],
    "bridal": [
        "South Indian bride full gold jewellery portrait",
        "Indian bride gold bridal set portrait",
        "Tamil bride temple jewellery portrait",
        "bridal portrait gold maang tikka close-up",
        "bride gold necklace earring set portrait",
        "bride in silk saree with gold jewellery",
        "bridal close-up face gold jewellery",
        "North Indian bride gold jewellery portrait",
        "Kerala bride gold jewellery portrait",
        "full bridal portrait gold jewellery",
    ],
    "earrings": [
        "woman gold jhumka earrings portrait",
        "woman gold hoop earrings portrait",
        "woman gold chandbali earrings portrait",
        "woman chandelier earrings portrait",
        "woman gold earrings three quarter portrait",
        "Indian woman gold kammal portrait",
        "woman long gold earrings portrait",
        "woman diamond earrings portrait",
    ],
    "bangles": [
        "woman hands with gold bangles",
        "Indian woman gold bangles wrist close-up",
        "woman bridal bangles hands close-up",
        "woman gold and glass bangles hands",
        "woman gold kada bangle close-up",
        "woman hands with bangles close-up",
        "woman gold bracelet wrist close-up",
        "woman multiple bangles portrait",
    ],
}

MODEL_LOOKS = [
    "elegant studio portrait", "natural smile portrait",
    "side profile portrait", "three quarter portrait",
    "close-up face portrait", "full upper body portrait",
]

MODEL_SAREE_LIST = [
    "in silk saree", "in bridal saree",
    "in South Indian saree", "in Kanchipuram saree",
]

# ─────────────────────────────────────────────────────────────
# 22. OFFICE MODELS
# ─────────────────────────────────────────────────────────────

OFFICE_MODELS = {
    "women": [
        "Indian woman in formal office wear portrait",
        "professional woman in blazer portrait",
        "businesswoman in formal suit portrait",
        "office woman in formal saree portrait",
        "professional woman corporate attire portrait",
        "woman in formal white shirt portrait",
        "corporate woman smart formal portrait",
        "office woman three quarter portrait",
        "professional woman confident pose portrait",
        "Indian businesswoman formal portrait",
    ],
    "men": [
        "Indian man in formal suit portrait",
        "businessman formal shirt trousers portrait",
        "professional man in blazer portrait",
        "office man formal kurta portrait",
        "corporate man suit and tie portrait",
        "professional Indian man formal portrait",
        "man formal white shirt portrait",
        "businessman confident pose portrait",
        "professional man three quarter portrait",
        "Indian corporate man formal portrait",
    ],
    "casual": [
        "Indian woman smart casual portrait",
        "woman in kurta and jeans portrait",
        "woman printed western top portrait",
        "girl smart casual dress portrait",
        "woman simple salwar kameez portrait",
        "young woman smart casual portrait",
        "woman linen shirt trousers portrait",
        "Indian girl modern casual portrait",
    ],
}

OFFICE_POSES = [
    "full body standing portrait", "side profile portrait",
    "three quarter portrait", "arms crossed professional",
    "relaxed smile portrait", "close-up headshot portrait",
]

# ─────────────────────────────────────────────────────────────
# 23. VEHICLES
# ─────────────────────────────────────────────────────────────

VEHICLES = {
    "hatchback": [
        "Maruti Alto front view", "Maruti Alto side profile",
        "Hyundai i20 front view", "Hyundai i20 side profile",
        "Maruti Swift front view", "Maruti Swift side profile",
        "Tata Tiago front view", "Tata Tiago side profile",
        "Maruti Wagon R front view", "Maruti Wagon R side profile",
        "Tata Punch front view", "Tata Punch side profile",
    ],
    "sedan": [
        "Honda City sedan front view", "Honda City side profile",
        "Maruti Dzire front view", "Maruti Dzire side profile",
        "Hyundai Verna front view", "Hyundai Verna side profile",
        "Honda Amaze front view", "Honda Amaze side profile",
    ],
    "suv": [
        "Mahindra Scorpio front view", "Mahindra Scorpio side profile",
        "Hyundai Creta front view", "Hyundai Creta side profile",
        "Kia Seltos front view", "Kia Seltos side profile",
        "Tata Nexon front view", "Tata Nexon side profile",
        "Mahindra Bolero front view", "Mahindra Bolero side profile",
        "Maruti Brezza front view", "Maruti Brezza side profile",
        "Toyota Fortuner front view", "Toyota Fortuner side profile",
    ],
    "mpv": [
        "Toyota Innova front view", "Toyota Innova side profile",
        "Mahindra Xylo front view", "Tata Ace front view",
        "Tata Ace side profile",
    ],
    "bikes_commuter": [
        "Hero Splendor front view", "Hero Splendor side profile",
        "Bajaj Pulsar 150 front view", "Bajaj Pulsar 150 side profile",
        "Honda Shine front view", "Honda Shine side profile",
        "TVS Apache 160 front view", "TVS Apache 160 side profile",
        "Honda Unicorn front view", "Honda Unicorn side profile",
    ],
    "bikes_royal_enfield": [
        "Royal Enfield Classic 350 front view",
        "Royal Enfield Classic 350 side profile",
        "Royal Enfield Bullet 350 front view",
        "Royal Enfield Bullet 350 side profile",
        "Royal Enfield Meteor 350 front view",
        "Royal Enfield Meteor 350 side profile",
        "Royal Enfield Himalayan front view",
        "Royal Enfield Himalayan side profile",
    ],
    "bikes_sports": [
        "Bajaj Pulsar NS200 front view", "Bajaj Pulsar NS200 side profile",
        "Yamaha R15 front view", "Yamaha R15 side profile",
        "KTM Duke 200 front view", "KTM Duke 200 side profile",
        "Bajaj Dominar 400 front view", "Bajaj Dominar 400 side profile",
    ],
    "scooter": [
        "Honda Activa front view", "Honda Activa side profile",
        "TVS Jupiter front view", "TVS Jupiter side profile",
        "Suzuki Access front view", "Suzuki Access side profile",
        "Yamaha Fascino front view", "Yamaha Fascino side profile",
    ],
    "auto_rickshaw": [
        "Indian auto rickshaw front view",
        "Indian auto rickshaw side profile",
        "auto rickshaw 3/4 front view",
        "auto rickshaw rear view",
        "yellow auto rickshaw front view",
        "electric auto rickshaw front view",
        "electric auto rickshaw side profile",
        "auto rickshaw low angle view",
        "auto rickshaw top aerial view",
        "auto rickshaw close-up front",
    ],
}

CAR_DETAILS = [
    "clean polished bodywork",
    "professional automotive photography",
    "showroom quality",
    "studio car photography",
    "commercial vehicle photography",
]

# ═══════════════════════════════════════════════════════════
# PROMPT ENGINE CLASS
# ═══════════════════════════════════════════════════════════

class PromptEngine:
    def make(self, subject, extra: str = "", variant: str = "base"):
        """
        One prompt-builder tool.

        variant="base"   -> ANGLES + PHOTO + BASE_SUFFIX (default, existing behavior)
        variant="animal" -> LIGHTING + QUALITY + ANIMAL_SUFFIX
        variant="model"  -> LIGHTING + QUALITY + MODEL_SUFFIX
        """
        parts = [subject]
        if extra:
            parts.append(extra)

        if variant == "base":
            a = random.choice(ANGLES)
            l = random.choice(LIGHTING)
            q = random.choice(QUALITY)
            s = random.choice(PHOTO)
            parts.extend([a, l, q, s, BASE_SUFFIX])
        elif variant == "animal":
            l = random.choice(LIGHTING)
            q = random.choice(QUALITY)
            parts.extend([l, q, ANIMAL_SUFFIX])
        elif variant == "model":
            l = random.choice(LIGHTING)
            q = random.choice(QUALITY)
            parts.extend([l, q, MODEL_SUFFIX])
        else:
            raise ValueError(f"Unknown prompt variant: {variant}")

        return ", ".join(parts)

    def add(self, prompts, cat, sub, text):
        prompts.append({
            "category": cat, "subcategory": sub,
            "prompt": text, "seed": random.randint(1, 999999)
        })

    # ── 1. POULTRY & ANIMALS ─────────────────────────────────
    def gen_animals(self):
        p = []
        ctxs = ["professional studio", "clean full body", "natural pose",
                "alert pose", "calm pose", "side profile"]
        for sub, items in POULTRY_ANIMALS.items():
            for item in items:
                for ctx in ctxs:
                    self.add(p, "poultry_animals", sub, self.make(item, ctx, variant="animal"))
        return p

    # ── 2. FISH & SEAFOOD ────────────────────────────────────
    def gen_fish(self):
        p = []
        for sub, items in FISH_SEAFOOD.items():
            for item in items:
                for ctx in FISH_CONTEXTS:
                    style = random.choice(FISH_STYLE)
                    self.add(p, "fish_seafood", sub, self.make(item, f"{ctx}, {style}"))
        return p

    # ── 3. EGGS ──────────────────────────────────────────────
    def gen_eggs(self):
        p = []
        for item in EGGS:
            for ctx in EGG_CONTEXTS:
                self.add(p, "eggs", "eggs", self.make(f"{item}, {ctx}"))
        return p

    # ── 4. FLOWERS ───────────────────────────────────────────
    def gen_flowers(self):
        p = []
        for sub, items in FLOWERS_SINGLE.items():
            for item in items:
                for ctx in FLOWER_CONTEXTS:
                    ph = random.choice(FLOWER_PHOTO)
                    self.add(p, "flowers", f"single_{sub}",
                             self.make(f"{item}, {ctx}", ph))
        for item in FLOWERS_GROUP:
            for ph in FLOWER_PHOTO:
                self.add(p, "flowers", "group_flowers", self.make(item, ph))
        return p

    # ── 5. FRUITS ────────────────────────────────────────────
    def gen_fruits(self):
        p = []
        styles = ["studio product photography", "overhead flat lay photography",
                  "natural light photography", "editorial photography"]
        for sub, items in FRUITS_SINGLE.items():
            for item in items:
                for ctx in FRUIT_CONTEXTS:
                    self.add(p, "fruits", f"single_{sub}", self.make(f"{item}, {ctx}"))
        for item in FRUITS_GROUP:
            for s in styles:
                self.add(p, "fruits", "group_fruits", self.make(item, s))
        return p

    # ── 6. VEGETABLES ────────────────────────────────────────
    def gen_vegetables(self):
        p = []
        styles = ["studio product photography", "overhead flat lay photography",
                  "natural light photography", "editorial photography"]
        for sub, items in VEGS_SINGLE.items():
            for item in items:
                for ctx in VEG_CONTEXTS:
                    self.add(p, "vegetables", f"single_{sub}", self.make(f"{item}, {ctx}"))
        for item in VEGS_GROUP:
            for s in styles:
                self.add(p, "vegetables", "group_vegetables", self.make(item, s))
        return p

    # ── 7. COOL DRINKS ───────────────────────────────────────
    def gen_drinks(self):
        p = []
        for sub, items in COOL_DRINKS.items():
            for item in items:
                for v in DRINK_VESSELS:
                    d = random.choice(DRINK_DETAILS)
                    self.add(p, "cool_drinks", sub, self.make(item, f"{v}, {d}"))
        return p

    # ── 8. INDIAN FOODS ──────────────────────────────────────
    def gen_indian_food(self):
        p = []
        for sub, items in INDIAN_FOODS.items():
            for item in items:
                for v in INDIAN_VESSELS:
                    a = random.choice(FOOD_ANGLES)
                    self.add(p, "indian_foods", sub, self.make(item, f"{v}, {a}"))
        return p

    # ── 9. WORLD FOODS ───────────────────────────────────────
    def gen_world_food(self):
        p = []
        for sub, items in WORLD_FOODS.items():
            for item in items:
                for v in WORLD_VESSELS:
                    a = random.choice(FOOD_ANGLES)
                    self.add(p, "world_foods", sub, self.make(item, f"{v}, {a}"))
        return p

    # ── 10. DAIRY ────────────────────────────────────────────
    def gen_dairy(self):
        p = []
        for sub, items in DAIRY.items():
            for item in items:
                for ctx in DAIRY_CONTEXTS:
                    self.add(p, "dairy_products", sub, self.make(f"{item}, {ctx}"))
        return p

    # ── 11. DRY FRUITS ───────────────────────────────────────
    def gen_dry_fruits(self):
        p = []
        for sub, items in DRY_FRUITS.items():
            for item in items:
                for ctx in DRY_FRUIT_CONTEXTS:
                    self.add(p, "dry_fruits_nuts", sub, self.make(f"{item}, {ctx}"))
        return p

    # ── 12. BAKERY ───────────────────────────────────────────
    def gen_bakery(self):
        p = []
        for sub, items in BAKERY.items():
            for item in items:
                for ctx in BAKERY_CONTEXTS:
                    self.add(p, "bakery_snacks", sub, self.make(f"{item}, {ctx}"))
        return p

    # ── 13. AYURVEDA ─────────────────────────────────────────
    def gen_ayurveda(self):
        p = []
        for sub, items in AYURVEDA.items():
            for item in items:
                for ctx in AYUR_CONTEXTS:
                    self.add(p, "ayurvedic_herbal", sub, self.make(f"{item}, {ctx}"))
        return p

    # ── 14. INDIAN SWEETS ────────────────────────────────────
    def gen_sweets(self):
        p = []
        for sub, items in INDIAN_SWEETS.items():
            for item in items:
                for ctx in SWEET_CONTEXTS:
                    self.add(p, "indian_sweets", sub, self.make(f"{item}, {ctx}"))
        return p

    # ── 15. STATIONERY GROUPS ────────────────────────────────
    def gen_stationery(self):
        p = []
        styles = ["flat lay photography", "top view overhead", "45 degree angle",
                  "studio product photography"]
        for item in STATIONERY_GROUPS:
            for s in styles:
                self.add(p, "stationery", "stationery_groups", self.make(item, s))
        return p

    # ── 16. KITCHEN VESSELS ──────────────────────────────────
    def gen_kitchen(self):
        p = []
        styles = ["flat lay photography", "top view overhead", "45 degree angle",
                  "studio product photography", "overhead view",
                  "close-up detail view"]
        for item in KITCHEN_GROUPS:
            for s in styles:
                self.add(p, "kitchen_vessels", "kitchen_groups", self.make(item, s))
        return p

    # ── 17. MOBILE ACCESSORIES ───────────────────────────────
    def gen_mobile(self):
        p = []
        for sub, items in MOBILE_ACCESSORIES.items():
            for item in items:
                for ctx in MOBILE_CONTEXTS:
                    self.add(p, "mobile_accessories", sub, self.make(f"{item}, {ctx}"))
        return p

    # ── 18. COMPUTER & ACCESSORIES ───────────────────────────
    def gen_computer(self):
        p = []
        for sub, items in COMPUTER_ACCESSORIES.items():
            for item in items:
                for ctx in COMPUTER_CONTEXTS:
                    self.add(p, "computer_accessories", sub, self.make(f"{item}, {ctx}"))
        return p

    # ── 19. FOOTWEAR ─────────────────────────────────────────
    def gen_footwear(self):
        p = []
        details = ["product photography", "studio shoe photography",
                   "clean surface", "commercial photography"]
        for sub, items in FOOTWEAR.items():
            for item in items:
                for v in SHOE_VIEWS:
                    d = random.choice(details)
                    self.add(p, "footwear", sub, self.make(f"{item}, {v}", d))
        return p

    # ── 20. INDIAN DRESS ─────────────────────────────────────
    def gen_dress(self):
        p = []
        styles = ["fashion photography", "textile studio photography",
                  "flat lay photography", "catalog photography"]
        for sub, items in INDIAN_DRESS.items():
            for item in items:
                for ctx in DRESS_CONTEXTS:
                    s = random.choice(styles)
                    self.add(p, "indian_dress", sub, self.make(f"{item}, {ctx}", s))
        return p

    # ── 21. JEWELLERY MODELS ─────────────────────────────────
    def gen_jewellery_models(self):
        p = []
        for sub, items in JEWELLERY_MODELS.items():
            for item in items:
                for look in MODEL_LOOKS:
                    saree = random.choice(MODEL_SAREE_LIST)
                    self.add(p, "jewellery_models", sub,
                             self.make(f"{item}, {saree}, {look}", variant="model"))
        return p

    # ── 22. OFFICE MODELS ────────────────────────────────────
    def gen_office_models(self):
        p = []
        for sub, items in OFFICE_MODELS.items():
            for item in items:
                for pose in OFFICE_POSES:
                    self.add(p, "office_models", sub,
                             self.make(f"{item}, {pose}", variant="model"))
        return p

    # ── 23. VEHICLES ─────────────────────────────────────────
    def gen_vehicles(self):
        p = []
        for sub, items in VEHICLES.items():
            for item in items:
                for d in CAR_DETAILS:
                    self.add(p, "vehicles", sub, self.make(item, d))
        return p

    # ═══════════════════════════════════════════════════════════
    # GENERATE ALL
    # ═══════════════════════════════════════════════════════════

    def generate_all_prompts(self):
        print("🎨 Guru Image Usha — PNG Library V5")
        print("=" * 60)
        all_p = []

        gens = [
            ("Poultry & Animals",      self.gen_animals),
            ("Fish & Seafood",         self.gen_fish),
            ("Eggs",                   self.gen_eggs),
            ("Flowers",                self.gen_flowers),
            ("Fruits",                 self.gen_fruits),
            ("Vegetables",             self.gen_vegetables),
            ("Cool Drinks",            self.gen_drinks),
            ("Indian Foods",           self.gen_indian_food),
            ("World Foods",            self.gen_world_food),
            ("Dairy Products",         self.gen_dairy),
            ("Dry Fruits & Nuts",      self.gen_dry_fruits),
            ("Bakery & Snacks",        self.gen_bakery),
            ("Ayurvedic / Herbal",     self.gen_ayurveda),
            ("Indian Sweets",          self.gen_sweets),
            ("Stationery Groups",      self.gen_stationery),
            ("Kitchen Vessels",        self.gen_kitchen),
            ("Mobile Accessories",     self.gen_mobile),
            ("Computer & Accessories", self.gen_computer),
            ("Footwear",               self.gen_footwear),
            ("Indian Dress",           self.gen_dress),
            ("Jewellery Models",       self.gen_jewellery_models),
            ("Office Models",          self.gen_office_models),
            ("Vehicles",               self.gen_vehicles),
        ]

        counts = {}
        for name, fn in gens:
            prev = len(all_p)
            all_p.extend(fn())
            c = len(all_p) - prev
            counts[name] = c
            print(f"  ✅ {name}: {c}")

        # Seed multiplier ×2
        variations = [
            "ultra sharp detail", "crisp clean quality",
            "true to life", "lifelike realistic detail",
            "fine surface detail", "photographic quality",
        ]
        extended = []
        for item in all_p:
            extended.append(item)
            copy = dict(item)
            copy["prompt"] = item["prompt"] + f", {random.choice(variations)}"
            copy["seed"]   = random.randint(100000, 999999)
            extended.append(copy)
        all_p = extended

        print(f"\n  🔁 Seed multiplier: {len(all_p)} total prompts")
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

        idx = {"total": len(prompts), "categories": list(by_cat.keys()),
               "files": [f"{c}.json" for c in by_cat]}
        with open(out / "index.json", "w", encoding="utf-8") as f:
            json.dump(idx, f, indent=2, ensure_ascii=False)

        print(f"\n✅ Saved {len(prompts)} prompts → {len(by_cat)} categories")
        return output_dir


def load_all_prompts(splits_dir="prompts/splits"):
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
        with open(fpath, encoding="utf-8") as f:
            all_p.extend(json.load(f))
    print(f"📦 Loaded {len(all_p)} prompts from {len(files)} files.")
    return all_p


if __name__ == "__main__":
    PromptEngine().save_prompts("prompts/splits")
