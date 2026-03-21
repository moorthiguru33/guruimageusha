"""
PNG Library — Prompt Engine V4 (GURU IMAGE USHA)
══════════════════════════════════════════════════════════
RULE    : Simple clear item names only. No confusing color/skin words.
          AI needs to know WHAT the item is — not get confused.
GROUPS  : Every item has single + group prompts (2, 3, 4 together, in bag etc.)
STYLE   : 100% Photorealistic studio photography
BG      : Solid light grey background
══════════════════════════════════════════════════════════
"""

import random
import json
from pathlib import Path

# ─────────────────────────────────────────────────────────────
# BASE SUFFIXES — unchanged, do not modify
# ─────────────────────────────────────────────────────────────

BASE_SUFFIX = (
    "isolated on solid light grey background, "
    "professional studio product photography, "
    "shot on Canon EOS R5 with 100mm macro lens, "
    "8k ultra high definition, photorealistic, "
    "razor sharp focus, studio strobe lighting with softbox, "
    "clean crisp edges, no shadows on background, centered composition"
)

ANIMAL_SUFFIX = (
    "isolated on solid light grey background, "
    "professional studio animal photography, "
    "shot on Canon EOS R5, 8k ultra high definition, "
    "photorealistic, razor sharp focus, natural animal pose, "
    "clean crisp edges, no shadows on background, centered full body"
)

MODEL_SUFFIX = (
    "isolated on solid light grey background, "
    "professional studio fashion portrait photography, "
    "shot on Canon EOS R5 with 85mm portrait lens, "
    "8k ultra high definition, photorealistic, "
    "razor sharp focus, studio strobe lighting with softbox, "
    "clean crisp edges, centered full body composition"
)

# ─────────────────────────────────────────────────────────────
# VARIATION BANKS
# ─────────────────────────────────────────────────────────────

CAMERA_ANGLES = [
    "front view straight on",
    "45 degree angle view",
    "top-down flat lay view",
    "side profile view",
    "3/4 perspective view",
    "close-up macro detail shot",
    "low angle hero view",
    "eye level view",
]

LIGHTING_STYLES = [
    "soft diffused studio lighting",
    "bright even fill lighting",
    "warm key light with cool fill",
    "high key bright studio lighting",
    "rim light with soft fill",
]

DETAIL_QUALITY = [
    "ultra fine surface detail",
    "lifelike realistic texture",
    "true-to-life rendering",
    "every detail clearly visible",
    "sharp crisp photographic quality",
]

PHOTO_STYLES = [
    "commercial product photography",
    "editorial magazine photography",
    "studio catalog photography",
    "high-end advertising photography",
]

# ─────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════
#  SIMPLE CLEAN PROMPTS — NO CONFUSING WORDS
#  RULE: Item name + how many + presentation only
# ══════════════════════════════════════════════════════════════
# ─────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────
# 1. LIVE POULTRY & ANIMALS
# ─────────────────────────────────────────────────────────────

ROOSTER_PROMPTS = [
    # Single
    "single rooster standing full body side view",
    "single rooster facing front view",
    "single rooster crowing with beak open",
    "single rooster with tail feathers visible",
    "single rooster close-up head portrait",
    "single rooster perched elevated view",
    "rooster full body 3/4 angle view",
    "rooster alert standing pose",
    # Group
    "two roosters standing together side by side",
    "three roosters group arranged together",
    "rooster and hen pair together",
]

BROILER_CHICKEN_PROMPTS = [
    # Single
    "single broiler chicken standing full body",
    "single white broiler chicken side view",
    "single broiler chicken facing front",
    "broiler chicken close-up head detail",
    "broiler chicken full body profile view",
    "broiler chicken resting on ground",
    # Group
    "two broiler chickens standing together",
    "three broiler chickens group together",
    "four broiler chickens arranged group",
    "flock of broiler chickens together",
]

GOAT_PROMPTS = [
    # Single
    "single goat standing full body side view",
    "single goat facing camera front view",
    "single goat with horns visible close-up",
    "single goat full body profile",
    "goat head portrait close-up",
    "single goat resting calm pose",
    "single goat grazing natural pose",
    "single young kid goat small",
    # Group
    "two goats standing together",
    "three goats group arranged",
    "mother goat with baby kid together",
    "four goats herd together",
]

QUAIL_PROMPTS = [
    # Single
    "single quail bird standing full body",
    "single quail side profile view",
    "single quail facing front",
    "quail close-up portrait head",
    "single quail resting calm",
    "single quail alert standing pose",
    # Group
    "two quail birds together",
    "three quail birds group",
    "five quail birds arranged group",
    "quail birds flock group together",
]

COW_PROMPTS = [
    # Single
    "single Indian cow standing full body side view",
    "single cow facing camera front view",
    "single cow full body profile",
    "cow head portrait close-up",
    "single cow resting lying down",
    "single cow with hump visible side view",
    "single cow alert standing pose",
    "single dairy cow full body",
    # Group
    "two cows standing together",
    "three cows group together",
    "cow with calf together",
    "herd of cows group together",
]

# ─────────────────────────────────────────────────────────────
# 2. RAW MEAT & EGGS
# ─────────────────────────────────────────────────────────────

RAW_CHICKEN_PROMPTS = [
    # Single cuts
    "whole raw chicken on plate",
    "raw chicken breast piece on plate",
    "raw chicken thigh piece on banana leaf",
    "raw chicken drumstick on plate",
    "raw chicken wings arranged on plate",
    "raw chicken curry cut pieces on banana leaf",
    "raw chicken leg piece on steel tray",
    "raw chicken liver on plate",
    "raw chicken pieces arranged on white plate",
    "raw whole chicken on banana leaf",
    # Group / multiple
    "multiple raw chicken pieces arranged on plate",
    "raw chicken pieces on banana leaf arranged",
    "raw chicken cuts variety on white plate",
    "raw chicken drumsticks four pieces arranged",
    "raw chicken wings six pieces arranged",
]

RAW_GOAT_PROMPTS = [
    # Single cuts
    "raw goat mutton pieces on banana leaf",
    "raw mutton curry cut pieces on plate",
    "raw goat leg piece on white plate",
    "raw mutton ribs on plate",
    "raw goat liver on plate",
    "raw mutton pieces on steel tray",
    "raw goat chops arranged on plate",
    "raw mutton keema minced on plate",
    # Group
    "multiple raw mutton pieces on banana leaf",
    "raw mutton variety cuts on white plate",
    "raw goat pieces arranged on plate",
    "raw mutton selection on banana leaf",
]

RAW_QUAIL_PROMPTS = [
    # Single
    "single whole raw quail on plate",
    "single raw quail on banana leaf",
    "single raw quail on white plate",
    "raw quail cleaned dressed on plate",
    # Group
    "two raw quail birds on banana leaf",
    "three raw quail birds arranged on plate",
    "four raw quail birds on plate",
    "six raw quail birds arranged on banana leaf",
    "raw quail birds group on white plate",
]

EGG_PROMPTS = [
    # Single
    "single chicken egg on white surface",
    "single brown egg on wooden surface",
    "single egg close-up macro detail",
    "cracked egg with yolk on plate",
    # Group
    "three eggs arranged together",
    "six eggs arranged in two rows",
    "dozen eggs in carton box",
    "eggs in wicker basket arranged",
    "pile of brown eggs together",
    "quail eggs small cluster together",
    "six quail eggs arranged on surface",
    "eggs scattered on wooden surface natural",
    "four eggs on grey surface",
    "eggs in white ceramic bowl",
]

# ─────────────────────────────────────────────────────────────
# 3. VEHICLES
# ─────────────────────────────────────────────────────────────

INDIAN_CAR_PROMPTS = {
    "hatchback": [
        "Maruti Suzuki Alto hatchback front view",
        "Maruti Suzuki Alto side profile view",
        "Hyundai i20 hatchback front 3/4 view",
        "Hyundai i20 side profile full view",
        "Maruti Swift hatchback front view",
        "Maruti Swift side profile view",
        "Tata Tiago hatchback front view",
        "Tata Tiago side profile view",
        "Maruti Wagon R front view",
        "Maruti Wagon R side profile view",
        "Tata Punch front 3/4 view",
        "Tata Punch side profile view",
    ],
    "sedan": [
        "Honda City sedan front 3/4 view",
        "Honda City sedan side profile view",
        "Maruti Dzire sedan front view",
        "Maruti Dzire side profile view",
        "Hyundai Verna sedan front 3/4 view",
        "Hyundai Verna side profile view",
        "Honda Amaze sedan front view",
        "Honda Amaze side profile view",
    ],
    "suv": [
        "Mahindra Scorpio SUV front 3/4 view",
        "Mahindra Scorpio side profile view",
        "Hyundai Creta SUV front view",
        "Hyundai Creta side profile view",
        "Kia Seltos SUV front 3/4 view",
        "Kia Seltos side profile view",
        "Tata Nexon SUV front view",
        "Tata Nexon side profile view",
        "Mahindra Bolero front view",
        "Mahindra Bolero side profile view",
        "Maruti Brezza front 3/4 view",
        "Maruti Brezza side profile view",
    ],
    "mpv": [
        "Toyota Innova MPV front 3/4 view",
        "Toyota Innova side profile view",
        "Mahindra Xylo MPV front view",
        "Mahindra Xylo side profile view",
        "Tata Ace mini truck front view",
        "Tata Ace mini truck side profile view",
    ],
}

BIKE_PROMPTS = {
    "commuter": [
        "Hero Splendor bike front view",
        "Hero Splendor side profile view",
        "Bajaj Pulsar 150 front 3/4 view",
        "Bajaj Pulsar 150 side profile view",
        "Honda Shine bike front view",
        "Honda Shine side profile view",
        "TVS Apache 160 front view",
        "TVS Apache 160 side profile view",
        "Honda Unicorn front view",
        "Honda Unicorn side profile view",
    ],
    "sports": [
        "Bajaj Pulsar NS200 front 3/4 view",
        "Bajaj Pulsar NS200 side profile view",
        "Yamaha R15 front view",
        "Yamaha R15 side profile view",
        "KTM Duke 200 front 3/4 view",
        "KTM Duke 200 side profile view",
        "Bajaj Dominar 400 front view",
        "Bajaj Dominar 400 side profile view",
    ],
    "royal_enfield": [
        "Royal Enfield Classic 350 front 3/4 view",
        "Royal Enfield Classic 350 side profile view",
        "Royal Enfield Bullet 350 front view",
        "Royal Enfield Bullet 350 side profile view",
        "Royal Enfield Meteor 350 front 3/4 view",
        "Royal Enfield Meteor 350 side profile view",
        "Royal Enfield Himalayan front view",
        "Royal Enfield Himalayan side profile view",
    ],
    "scooter": [
        "Honda Activa scooter front view",
        "Honda Activa scooter side profile view",
        "TVS Jupiter scooter front view",
        "TVS Jupiter scooter side profile view",
        "Suzuki Access scooter front view",
        "Suzuki Access scooter side profile view",
        "Yamaha Fascino scooter front view",
        "Yamaha Fascino scooter side profile view",
    ],
}

AUTO_RICKSHAW_PROMPTS = [
    "Indian auto rickshaw front view",
    "Indian auto rickshaw side profile view",
    "Indian auto rickshaw 3/4 front view",
    "Indian auto rickshaw rear view",
    "yellow auto rickshaw front view",
    "yellow auto rickshaw side profile",
    "auto rickshaw low angle hero shot",
    "auto rickshaw top aerial view",
    "electric auto rickshaw front view",
    "electric auto rickshaw side profile",
    "auto rickshaw with passenger seat visible",
    "auto rickshaw close-up front detail",
]

CAR_ANGLES = [
    "front 3/4 view",
    "side profile full view",
    "rear 3/4 view",
    "front straight on view",
    "low angle hero shot",
    "top aerial view",
]

# ─────────────────────────────────────────────────────────────
# 4. FLOWERS
# ─────────────────────────────────────────────────────────────

FLOWER_SINGLE_PROMPTS = {
    "rose": [
        "single red rose flower",
        "single pink rose flower",
        "single white rose flower",
        "single yellow rose flower",
        "single orange rose flower",
        "single dark red rose flower",
        "red rose bud close-up",
        "rose flower with green leaves",
        "rose flower top view",
        "rose flower side view",
    ],
    "lotus": [
        "single pink lotus flower open",
        "single white lotus flower open",
        "single lotus flower bud",
        "lotus flower top view",
        "lotus flower side view",
        "lotus flower with green leaf",
    ],
    "jasmine": [
        "jasmine flower cluster white",
        "jasmine flower bunch fresh",
        "jasmine single flower close-up",
        "jasmine flowers on stem",
        "jasmine flower top view",
        "jasmine garland fresh",
    ],
    "marigold": [
        "single orange marigold flower",
        "single yellow marigold flower",
        "marigold flower top view",
        "marigold flower side view",
        "marigold flower close-up",
        "marigold bunch tied together",
    ],
    "sunflower": [
        "single sunflower face view front",
        "single sunflower side view",
        "sunflower close-up center detail",
        "sunflower with stem and leaves",
        "sunflower top view",
        "sunflower bud just opening",
    ],
    "hibiscus": [
        "single red hibiscus flower open",
        "single yellow hibiscus flower",
        "single pink hibiscus flower",
        "hibiscus flower close-up",
        "hibiscus flower side view",
        "hibiscus flower top view",
    ],
    "lily": [
        "single white lily flower",
        "single pink lily flower",
        "lily flower close-up",
        "lily flower side view",
        "lily flower with stem",
        "lily flower top view",
    ],
    "orchid": [
        "single purple orchid flower",
        "single white orchid flower",
        "single pink orchid flower",
        "orchid flower close-up",
        "orchid flower side view",
        "orchid on stem multiple blooms",
    ],
}

FLOWER_GROUP_PROMPTS = [
    "bunch of red roses arranged together",
    "bouquet of mixed flowers colorful",
    "three roses arranged together",
    "five roses bouquet together",
    "bunch of marigolds tied together",
    "mixed flower bouquet arranged",
    "jasmine and rose mixed bunch",
    "flowers in small glass vase",
    "flower arrangement flat lay top view",
    "bunch of sunflowers together three",
    "roses and jasmine mixed bouquet",
    "marigold garland and loose flowers",
    "lotus flowers two together",
    "hibiscus flowers three arranged",
    "lily flowers bunch together",
    "orchid spray multiple blooms on stem",
    "mixed Indian flowers arranged bunch",
    "wedding flower bouquet white flowers",
    "festival flowers mixed colorful bunch",
    "flower basket overflowing variety",
    "dozen roses bouquet arranged",
    "temple flowers marigold jasmine bunch",
    "flower vendor bundle arranged",
    "fresh flowers flat lay overhead view",
    "colorful mixed flowers group arranged",
]

FLOWER_CONTEXTS = [
    "studio photography close-up",
    "with morning dew drops on petals",
    "with fresh green leaves",
    "freshly cut stem visible",
    "in full bloom",
    "top view overhead",
]

# ─────────────────────────────────────────────────────────────
# 5. FRUITS
# ─────────────────────────────────────────────────────────────

FRUIT_SINGLE_PROMPTS = {
    "mango": [
        "single mango whole fruit",
        "mango cut in half showing inside",
        "mango sliced pieces arranged",
        "mango top view",
        "ripe mango close-up",
        "mango with leaf attached",
        "small green mango unripe",
        "mango cross section view",
    ],
    "banana": [
        "single banana whole",
        "single banana peeled",
        "banana close-up",
        "banana top view",
        "green banana unripe",
        "ripe banana yellow",
    ],
    "apple": [
        "single apple whole",
        "apple cut in half showing inside",
        "apple slice arranged",
        "apple top view",
        "apple close-up",
        "apple with stem",
    ],
    "watermelon": [
        "whole watermelon",
        "watermelon slice triangular",
        "watermelon half cut open",
        "watermelon cubes arranged",
        "watermelon round slice flat",
        "watermelon close-up flesh",
    ],
    "grapes": [
        "bunch of grapes",
        "grapes cluster close-up",
        "grapes on vine",
        "grapes top view",
        "green grapes bunch",
        "purple grapes bunch",
    ],
    "orange": [
        "single orange whole fruit",
        "orange cut in half showing inside",
        "orange slice round",
        "orange segments arranged",
        "orange top view",
        "orange close-up skin texture",
    ],
    "lemon": [
        "single lemon whole",
        "lemon cut in half",
        "lemon slice round",
        "lemon top view",
        "lemon close-up",
        "lemon with leaf",
    ],
    "coconut": [
        "green tender coconut whole",
        "coconut with straw",
        "coconut cut open showing inside",
        "mature coconut whole brown",
        "coconut half showing white flesh",
        "coconut top view",
    ],
    "papaya": [
        "whole papaya fruit",
        "papaya cut in half showing inside seeds",
        "papaya sliced pieces",
        "papaya top view",
        "papaya close-up flesh",
        "small papaya whole",
    ],
    "pomegranate": [
        "whole pomegranate fruit",
        "pomegranate cut in half showing seeds",
        "pomegranate seeds scattered",
        "pomegranate top view",
        "pomegranate close-up",
        "pomegranate quarter cut",
    ],
    "pineapple": [
        "whole pineapple with crown",
        "pineapple slice round",
        "pineapple cut in half",
        "pineapple chunks arranged",
        "pineapple top view",
        "pineapple close-up skin",
    ],
    "guava": [
        "single guava whole fruit",
        "guava cut in half showing inside",
        "guava slice arranged",
        "guava top view",
        "guava close-up",
        "guava with leaf",
    ],
    "other_fruits": [
        "single strawberry",
        "kiwi cut in half showing inside",
        "dragon fruit cut in half",
        "fig cut in half showing inside",
        "chikoo sapodilla whole fruit",
        "jackfruit cut piece",
        "custard apple whole fruit",
        "plum whole fruit",
        "peach whole fruit",
        "cherry pair with stem",
    ],
}

FRUIT_GROUP_PROMPTS = [
    # Specific groups as user requested
    "3 tomatoes arranged together on surface",
    "single banana on surface",
    "bunch of 6 bananas together",
    "2 bananas together",
    "3 mangoes arranged together",
    "2 mangoes with one cut open",
    "pile of mangoes together",
    "3 apples arranged together",
    "4 apples grouped together",
    "2 oranges with one sliced",
    "3 oranges arranged",
    "2 lemons together",
    "3 lemons arranged",
    "watermelon with slice cut beside it",
    "3 guavas arranged together",
    "bunch of grapes and 2 apples together",
    "mixed fruit basket arrangement",
    "all fruits variety flat lay collection",
    "tropical fruits collection arranged",
    "Indian fruits variety arranged together",
    "fruit platter cut fruits arranged",
    "4 pomegranates arranged together",
    "3 papayas together",
    "2 pineapples arranged",
    "coconuts three arranged together",
    "mixed citrus fruits lemon orange lime together",
    "strawberries pile together",
    "kiwi and strawberry together arranged",
    "fruit market style mixed arrangement",
    "seasonal fruits collection flat lay",
]

FRUIT_CONTEXTS = [
    "on white surface",
    "on wooden surface",
    "on grey surface",
    "top view overhead",
    "close-up detail",
    "with water droplets fresh",
    "with leaves attached natural",
    "cut open showing inside",
]

# ─────────────────────────────────────────────────────────────
# 6. VEGETABLES
# ─────────────────────────────────────────────────────────────

VEG_SINGLE_PROMPTS = {
    "tomato": [
        "single tomato whole",
        "tomato cut in half showing inside",
        "tomato top view",
        "tomato close-up",
        "tomato with stem and leaf",
        "tomato slice round",
        "small cherry tomatoes cluster",
        "tomato 45 degree view",
    ],
    "potato": [
        "single potato whole",
        "potato cut in half showing inside white flesh",
        "potato top view",
        "potato close-up skin texture",
        "baby potato small whole",
        "potato 45 degree view",
        "potato on wooden surface",
    ],
    "sweet_potato": [
        "single sweet potato whole",
        "sweet potato cut in half showing orange flesh",
        "sweet potato top view",
        "sweet potato close-up skin",
        "sweet potato side view",
        "sweet potato 45 degree view",
    ],
    "brinjal": [
        "single brinjal eggplant whole",
        "brinjal cut in half showing inside",
        "brinjal top view",
        "brinjal close-up skin texture",
        "brinjal side view",
        "round brinjal variety whole",
        "long brinjal whole",
        "brinjal with stem attached",
    ],
    "onion": [
        "single onion whole",
        "onion cut in half showing layers",
        "onion top view",
        "onion close-up skin",
        "onion slice rings arranged",
        "small shallots cluster",
        "spring onion bunch",
    ],
    "tomato_varieties": [
        "single red tomato ripe",
        "tomato on vine whole",
        "large beefsteak tomato",
        "roma tomato oval",
        "cherry tomatoes small cluster",
        "heirloom tomato cross section",
    ],
    "carrot": [
        "single carrot whole with top",
        "carrot cut in half",
        "carrot slice rounds",
        "carrot top view",
        "carrot close-up texture",
        "baby carrots small bunch",
    ],
    "capsicum": [
        "single green capsicum whole",
        "single red capsicum whole",
        "single yellow capsicum whole",
        "capsicum cut in half showing inside",
        "capsicum top view",
        "capsicum close-up skin",
    ],
    "okra": [
        "single okra ladyfinger whole",
        "okra bunch fresh",
        "okra cut open showing inside",
        "okra top view",
        "okra close-up",
        "okra flat lay arranged",
    ],
    "cucumber": [
        "single cucumber whole",
        "cucumber slice rounds arranged",
        "cucumber cut in half lengthwise",
        "cucumber top view",
        "cucumber close-up skin",
        "cucumber with flower end",
    ],
    "beans": [
        "green beans cluster fresh",
        "beans flat lay arranged",
        "beans top view",
        "beans close-up",
        "beans cut showing inside",
        "cluster beans bunch",
    ],
    "other_veggies": [
        "cauliflower head whole",
        "broccoli head whole",
        "cabbage head whole",
        "bitter gourd whole",
        "drumstick long vegetable whole",
        "ginger root whole",
        "garlic bulb whole",
        "spinach bunch fresh",
        "pumpkin whole",
        "pumpkin cut in half showing inside",
    ],
}

VEG_GROUP_PROMPTS = [
    # Specific groups as user requested
    "3 tomatoes arranged together",
    "4 tomatoes grouped together",
    "tomatoes in small bowl arranged",
    "3 brinjals arranged together",
    "4 brinjals grouped together",
    "brinjal and tomato together arranged",
    "3 potatoes arranged together",
    "potatoes in jute bag",
    "potatoes in basket arranged",
    "pile of potatoes together",
    "4 sweet potatoes arranged together",
    "sweet potatoes in basket",
    "3 onions arranged together",
    "pile of onions together",
    "onions in jute bag",
    "3 carrots arranged together",
    "carrot bunch tied together",
    "3 cucumbers arranged together",
    "capsicum three colors together",
    "okra bunch arranged together",
    "beans pile arranged",
    "mixed vegetables flat lay collection",
    "Indian cooking vegetables arranged together",
    "vegetable basket overflowing variety",
    "vegetables in jute bag arranged",
    "mixed vegetables market style",
    "cauliflower broccoli together",
    "garlic onion ginger three together",
    "mixed green vegetables bunch",
    "vegetable platter variety arranged",
]

VEG_CONTEXTS = [
    "on white surface",
    "on wooden surface",
    "on grey surface",
    "top view overhead",
    "close-up detail texture",
    "with water droplets fresh",
    "with stem and leaf attached",
    "cut open showing inside",
]

# ─────────────────────────────────────────────────────────────
# 7. COOL DRINKS
# ─────────────────────────────────────────────────────────────

DRINK_PROMPTS = {
    "mojito": [
        "mojito drink in tall glass with mint and lime",
        "mint mojito with crushed ice in glass",
        "mojito drink with straw and lime slice",
        "mojito in mason jar with mint",
        "mojito close-up glass condensation",
        "mojito top view overhead",
        "two mojito glasses together",
        "mojito with fruit garnish",
    ],
    "lemon_soda": [
        "lemon soda in glass with ice",
        "nimbu pani lemon water in glass",
        "lemon soda with lemon slice on rim",
        "fresh lime soda fizzy in glass",
        "lemon soda with straw in glass",
        "lemon soda top view overhead",
        "masala lemon soda in glass",
        "lemon soda close-up glass condensation",
        "two lemon soda glasses together",
        "lemon soda in clay kulhad",
    ],
    "lassi": [
        "mango lassi in tall glass",
        "plain lassi in brass glass",
        "sweet lassi frothy in glass",
        "lassi with cream on top",
        "lassi in clay kulhad earthen cup",
        "lassi close-up frothy surface",
        "lassi top view overhead",
        "two lassi glasses together",
        "pink rose lassi in glass",
        "lassi with dry fruit garnish",
    ],
    "tender_coconut": [
        "tender coconut with straw whole",
        "green coconut with colorful straw",
        "tender coconut cut open with spoon",
        "tender coconut top view",
        "two tender coconuts with straws",
        "three coconuts arranged together",
        "coconut water in glass with coconut",
        "tender coconut close-up",
        "tender coconut on white surface",
        "tender coconut with paper straw",
    ],
    "fresh_juice": [
        "fresh orange juice in glass with orange slice",
        "sugarcane juice in glass fresh",
        "watermelon juice in glass",
        "pomegranate juice in glass",
        "carrot juice in glass",
        "mixed fruit juice colorful in glass",
        "fresh juice with fruit beside glass",
        "juice glass top view overhead",
        "two juice glasses together",
        "fresh juice with straw in glass",
    ],
    "buttermilk": [
        "buttermilk chaas in glass",
        "buttermilk in brass tumbler",
        "buttermilk in clay pot",
        "buttermilk with curry leaves garnish",
        "buttermilk frothy in glass",
        "buttermilk top view overhead",
        "two buttermilk glasses together",
        "masala buttermilk in glass",
        "buttermilk close-up frothy",
        "buttermilk in tall glass with ice",
    ],
}

DRINK_VESSELS = [
    "in tall clear glass",
    "in brass tumbler traditional",
    "in clay kulhad earthen cup",
    "in mason jar glass",
    "in ceramic glass",
    "in tall glass with ice cubes visible",
]

DRINK_DETAILS = [
    "condensation droplets on cold glass",
    "with fresh garnish on top",
    "with colorful straw inserted",
    "ice cubes clearly visible",
    "frothy top surface",
]

# ─────────────────────────────────────────────────────────────
# 8. INDIAN FOODS
# ─────────────────────────────────────────────────────────────

INDIAN_FOOD_PROMPTS = {
    "biryani": [
        "biryani in bowl with rice and meat",
        "biryani served on banana leaf",
        "biryani in clay pot",
        "biryani close-up with garnish",
        "biryani top view overhead",
        "chicken biryani in bowl",
        "mutton biryani on plate",
        "biryani with raita on side",
        "biryani on steel thali",
        "biryani steam rising from bowl",
    ],
    "dosa": [
        "masala dosa on plate with chutneys",
        "dosa on banana leaf",
        "crispy dosa with sambar bowl",
        "dosa close-up texture",
        "dosa top view overhead",
        "set dosa stack on plate",
        "egg dosa on plate",
        "dosa with coconut chutney",
        "dosa folded on plate",
        "large paper dosa on plate",
    ],
    "idly": [
        "idly on plate with sambar",
        "idly on banana leaf with chutneys",
        "idly stack three pieces on plate",
        "idly close-up texture",
        "idly top view overhead",
        "mini idly small on plate",
        "idly with sambar bowl beside",
        "idly with coconut chutney",
        "four idly on steel plate",
        "idly with podi powder",
    ],
    "parotta": [
        "parotta on plate layered",
        "parotta on banana leaf",
        "parotta close-up layers visible",
        "parotta top view overhead",
        "two parotta on plate",
        "parotta with chicken salna side",
        "parotta with kurma side",
        "kothu parotta on plate",
        "parotta stack visible layers",
        "hot parotta on plate fresh",
    ],
    "curry": [
        "chicken curry in bowl",
        "mutton curry in clay pot",
        "fish curry in bowl",
        "egg curry in bowl",
        "prawn curry in bowl",
        "curry close-up overhead view",
        "curry with rice on plate",
        "crab masala in plate",
        "chicken curry on banana leaf",
        "thick curry in steel bowl",
    ],
    "rice_dishes": [
        "lemon rice on banana leaf",
        "curd rice in bowl",
        "tomato rice on plate",
        "biryani rice in clay pot",
        "plain rice with ghee in bowl",
        "pongal in bowl",
        "sambar rice on plate",
        "ghee rice in bowl",
        "coconut rice on banana leaf",
        "tamarind rice on plate",
    ],
    "snacks": [
        "samosa three pieces on plate",
        "medu vada two pieces on plate",
        "murukku on plate",
        "pakora on plate",
        "bajji on plate",
        "snacks close-up overhead view",
        "banana chips on plate",
        "masala vada on plate",
        "bread pakora on plate",
        "aloo tikki on plate",
    ],
    "sweets": [
        "gulab jamun in bowl with syrup",
        "mysore pak on plate",
        "jalebi on plate",
        "rava kesari in bowl",
        "ladoo three pieces on plate",
        "sweets close-up overhead view",
        "kaju katli on plate",
        "rasgulla in bowl",
        "kheer in bowl",
        "coconut burfi on plate",
    ],
}

INDIAN_FOOD_VESSELS = [
    "on banana leaf",
    "in steel thali",
    "in ceramic bowl",
    "in clay pot",
    "in copper bowl",
    "on white plate",
]

FOOD_ANGLES = [
    "overhead flat lay view",
    "45 degree angled shot",
    "front view",
    "close-up macro",
    "side view",
]

# ─────────────────────────────────────────────────────────────
# 9. WORLD FOODS
# ─────────────────────────────────────────────────────────────

WORLD_FOOD_PROMPTS = {
    "pizza": [
        "pizza whole on wooden board",
        "pizza slice single piece",
        "pizza top view overhead",
        "pizza close-up cheese stretch",
        "pizza side view showing layers",
        "two pizza slices arranged",
        "pizza in box open",
        "pizza fresh from oven",
        "mini pizza personal size",
        "pizza with toppings visible",
        "pizza 45 degree angle view",
        "pizza on white plate",
    ],
    "burger": [
        "burger whole on plate",
        "burger cut in half showing layers",
        "burger close-up side view",
        "burger top view overhead",
        "burger with fries on plate",
        "burger 45 degree angle",
        "burger on wooden board",
        "double burger stacked",
        "burger unwrapped showing inside",
        "burger with sauce dripping",
        "two burgers arranged",
        "burger close-up macro",
    ],
    "fried_chicken": [
        "fried chicken piece on plate",
        "fried chicken drumstick single",
        "fried chicken bucket full",
        "fried chicken strips on plate",
        "fried chicken close-up crispy",
        "fried chicken top view overhead",
        "fried chicken with dip sauce",
        "four fried chicken pieces arranged",
        "fried chicken on wooden board",
        "fried chicken 45 degree angle",
        "fried chicken sandwich on plate",
        "crispy fried chicken pieces arranged",
    ],
    "french_fries": [
        "french fries in box",
        "french fries in paper cone",
        "french fries on plate",
        "french fries close-up",
        "french fries top view overhead",
        "large portion fries in box",
        "fries with dip sauce on side",
        "curly fries on plate",
        "waffle fries on plate",
        "thick cut fries on board",
        "cheese fries loaded on plate",
        "fries two boxes arranged",
    ],
    "noodles": [
        "noodles in bowl with chopsticks",
        "noodles top view overhead",
        "noodles close-up texture",
        "noodles on plate",
        "ramen bowl with egg on top",
        "stir fried noodles in bowl",
        "noodles with vegetables in bowl",
        "noodles 45 degree angle",
        "noodle bowl steam rising",
        "noodles on plate with sauce",
        "noodles close-up with garnish",
        "noodles in ceramic bowl",
    ],
    "fried_rice": [
        "fried rice in bowl",
        "fried rice on plate",
        "fried rice top view overhead",
        "fried rice close-up",
        "fried rice 45 degree angle",
        "fried rice in wok",
        "fried rice with egg visible",
        "fried rice with vegetables",
        "fried rice with chopsticks",
        "fried rice on banana leaf",
        "fried rice in ceramic bowl",
        "fried rice with garnish",
    ],
    "chinese": [
        "spring rolls on plate crispy",
        "dim sum in bamboo basket",
        "chicken manchurian in bowl",
        "gobi manchurian on plate",
        "wonton soup in bowl",
        "spring rolls close-up",
        "dim sum top view overhead",
        "chinese food on plate arranged",
        "soup bowl with dumplings",
        "chinese stir fry on plate",
        "spring rolls two pieces on plate",
        "chinese noodles in bowl",
    ],
}

WORLD_FOOD_VESSELS = [
    "on white plate",
    "on wooden board",
    "in ceramic bowl",
    "on slate board",
    "in paper box",
    "in bamboo basket",
]

# ─────────────────────────────────────────────────────────────
# 10. FOOTWEAR
# ─────────────────────────────────────────────────────────────

FOOTWEAR_PROMPTS = {
    "chappals": [
        "single chappal sandal side view",
        "pair of chappals front view",
        "chappals top view flat lay",
        "leather chappal close-up",
        "rubber chappal pair",
        "traditional chappal side view",
        "chappal sole detail view",
        "chappal pair 45 degree angle",
        "two chappals arranged",
        "chappal on white surface",
    ],
    "sandals": [
        "single sandal side view",
        "pair of sandals front view",
        "sandals top view flat lay",
        "leather sandal close-up",
        "strappy sandal pair",
        "sandal 45 degree angle",
        "sandal sole detail view",
        "ladies sandal pair arranged",
        "sandal on white surface",
        "two sandals arranged",
    ],
    "shoes": [
        "single shoe side profile view",
        "pair of shoes front view",
        "shoes top view flat lay",
        "leather shoe close-up texture",
        "formal shoes pair arranged",
        "shoe 45 degree angle",
        "shoe sole detail view",
        "shoes on white surface",
        "shoes pair side by side",
        "shoe lace detail close-up",
    ],
    "heels": [
        "single heel shoe side view",
        "pair of heels front view",
        "heels top view flat lay",
        "stiletto heel close-up",
        "heels 45 degree angle",
        "block heel shoe pair",
        "heels sole detail view",
        "ladies heels pair arranged",
        "heels on white surface",
        "pointed heel shoe side view",
    ],
    "sports_shoes": [
        "single sports shoe side view",
        "pair of sports shoes front view",
        "sports shoes top view flat lay",
        "running shoes pair arranged",
        "sports shoe sole detail",
        "sports shoes 45 degree angle",
        "sneakers pair side by side",
        "sports shoes on white surface",
        "running shoes close-up texture",
        "sneakers top view overhead",
    ],
    "kids_footwear": [
        "kids school shoes pair",
        "children sneakers pair front view",
        "kids sandal pair arranged",
        "baby shoes tiny pair",
        "kids shoes top view flat lay",
        "children shoes side view",
        "kids footwear pair arranged",
    ],
}

SHOE_VIEWS = [
    "side profile view",
    "front view",
    "top view flat lay",
    "45 degree angle",
    "sole detail view",
    "heel close-up",
]

# ─────────────────────────────────────────────────────────────
# 11. INDIAN DRESS
# ─────────────────────────────────────────────────────────────

DRESS_PROMPTS = {
    "saree": [
        "saree neatly folded showing fabric",
        "saree draped showing full fabric",
        "saree flat lay full garment",
        "silk saree folded with border visible",
        "saree close-up embroidery detail",
        "saree pallu end detail close-up",
        "bridal saree folded heavy embroidery",
        "cotton saree folded lightweight",
        "saree zari border close-up",
        "saree fabric texture close-up",
        "Kanchipuram saree folded",
        "Banarasi saree folded",
    ],
    "salwar_kameez": [
        "salwar kameez set flat lay",
        "salwar suit folded arranged",
        "anarkali suit flat lay",
        "salwar kameez fabric detail",
        "salwar kameez embroidery close-up",
        "palazzo suit flat lay",
        "salwar kameez on hanger",
        "printed salwar kameez flat lay",
        "embroidered salwar kameez",
        "salwar kameez top view overhead",
    ],
    "lehenga": [
        "lehenga skirt flat lay",
        "bridal lehenga folded",
        "lehenga embroidery close-up",
        "lehenga choli set flat lay",
        "lehenga fabric detail",
        "lehenga top view overhead",
    ],
    "kurta": [
        "mens kurta folded flat lay",
        "kurta on hanger full view",
        "kurta fabric detail close-up",
        "embroidered kurta flat lay",
        "silk kurta folded",
        "kurta pajama set arranged",
        "sherwani flat lay",
        "kurta top view overhead",
        "printed kurta flat lay",
        "plain white kurta folded",
    ],
    "kids_dress": [
        "kids lehenga choli flat lay",
        "children kurta pajama set flat lay",
        "baby girl frock flat lay",
        "kids ethnic wear flat lay",
        "boys sherwani flat lay",
        "girls salwar kameez flat lay",
        "kids dress fabric detail",
        "children traditional dress flat lay",
        "kids festive wear top view",
        "infant Indian dress tiny",
    ],
}

DRESS_CONTEXTS = [
    "neatly folded on surface",
    "draped showing fabric",
    "flat lay top view",
    "hanging full length",
    "embroidery detail close-up",
    "fabric texture close-up",
]

# ─────────────────────────────────────────────────────────────
# 12. JEWELLERY MODELS
# ─────────────────────────────────────────────────────────────

JEWELLERY_MODEL_PROMPTS = {
    "necklace_models": [
        "Indian woman wearing gold necklace portrait",
        "South Indian woman gold necklace studio portrait",
        "woman with traditional gold necklace close-up",
        "woman wearing heavy gold necklace in saree",
        "woman gold necklace three quarter portrait",
        "woman wearing layered gold necklace",
        "woman gold necklace side profile portrait",
        "Indian woman gold temple necklace portrait",
        "woman wearing gold chain necklace",
        "woman gold necklace smiling portrait",
    ],
    "bridal_models": [
        "South Indian bride full gold jewellery studio portrait",
        "Indian bride with gold bridal set portrait",
        "Tamil bride temple jewellery full set portrait",
        "bridal portrait with gold maang tikka close-up",
        "bride gold necklace earring set portrait",
        "Indian bridal jewellery model full portrait",
        "bride in silk saree with gold jewellery",
        "bridal close-up face gold jewellery portrait",
        "North Indian bride gold jewellery portrait",
        "Kerala bride gold jewellery portrait",
    ],
    "earring_models": [
        "woman wearing gold jhumka earrings portrait",
        "woman gold hoop earrings close-up portrait",
        "woman gold chandbali earrings portrait",
        "woman chandelier earrings side view portrait",
        "woman gold earrings three quarter portrait",
        "Indian woman gold kammal earrings portrait",
        "woman earrings close-up face portrait",
        "woman long gold earrings portrait",
    ],
    "bangle_models": [
        "woman hands with gold bangles close-up",
        "Indian woman wearing gold bangles wrist",
        "woman bridal bangles hands close-up",
        "woman hands gold and glass bangles",
        "woman gold kada bangle wrist close-up",
        "woman hands with bangles henna design",
        "woman gold bracelet wrist close-up",
        "woman multiple bangles hands portrait",
    ],
}

MODEL_LOOKS = [
    "elegant studio portrait",
    "natural smile portrait",
    "side profile graceful pose",
    "three quarter face portrait",
    "close-up face portrait",
    "full upper body portrait",
]

MODEL_SAREE = [
    "in silk saree",
    "in bridal saree",
    "in traditional South Indian saree",
    "in Kanchipuram saree",
]

# ─────────────────────────────────────────────────────────────
# 13. OFFICE MODELS
# ─────────────────────────────────────────────────────────────

OFFICE_MODEL_PROMPTS = {
    "women_office": [
        "Indian woman in formal office wear portrait",
        "professional woman in blazer and trousers portrait",
        "businesswoman in formal suit portrait",
        "office woman in formal saree portrait",
        "professional Indian woman corporate attire portrait",
        "woman in formal white shirt office portrait",
        "corporate woman smart formal wear portrait",
        "office woman three quarter body portrait",
        "professional woman confident pose portrait",
        "Indian businesswoman formal attire full portrait",
    ],
    "men_formal": [
        "Indian man in formal suit portrait",
        "businessman in formal shirt and trousers portrait",
        "professional man in blazer portrait",
        "office man in formal kurta portrait",
        "corporate man in suit and tie portrait",
        "professional Indian man formal attire portrait",
        "man in formal white shirt portrait",
        "businessman confident pose portrait",
        "professional man three quarter portrait",
        "Indian corporate man formal portrait",
    ],
    "casual_smart": [
        "Indian woman smart casual wear portrait",
        "woman in kurta and jeans portrait",
        "woman in printed western top portrait",
        "girl in casual smart dress portrait",
        "woman in simple salwar kameez portrait",
        "young woman smart casual Indian portrait",
        "woman in linen shirt trousers portrait",
        "Indian girl modern casual portrait",
    ],
}

MODEL_POSES_OFFICE = [
    "confident standing full body portrait",
    "side profile standing portrait",
    "three quarter body view portrait",
    "arms crossed professional pose portrait",
    "natural relaxed smile portrait",
    "close-up portrait headshot",
]

# ─────────────────────────────────────────────────────────────
# PROMPT ENGINE CLASS
# ─────────────────────────────────────────────────────────────

class PromptEngine:

    def __init__(self):
        pass

    def make_prompt(self, subject, extra=""):
        angle   = random.choice(CAMERA_ANGLES)
        light   = random.choice(LIGHTING_STYLES)
        quality = random.choice(DETAIL_QUALITY)
        style   = random.choice(PHOTO_STYLES)
        parts   = [subject]
        if extra:
            parts.append(extra)
        parts.extend([angle, light, quality, style, BASE_SUFFIX])
        return ", ".join(parts)

    def make_animal_prompt(self, subject, extra=""):
        light   = random.choice(LIGHTING_STYLES)
        quality = random.choice(DETAIL_QUALITY)
        parts   = [subject]
        if extra:
            parts.append(extra)
        parts.extend([light, quality, ANIMAL_SUFFIX])
        return ", ".join(parts)

    def make_model_prompt(self, subject, extra=""):
        light   = random.choice(LIGHTING_STYLES)
        quality = random.choice(DETAIL_QUALITY)
        parts   = [subject]
        if extra:
            parts.append(extra)
        parts.extend([light, quality, MODEL_SUFFIX])
        return ", ".join(parts)

    # ── 1. POULTRY & ANIMALS ─────────────────────────────────
    def generate_poultry_animal_prompts(self):
        prompts = []
        all_animals = [
            ("rooster",         ROOSTER_PROMPTS),
            ("broiler_chicken", BROILER_CHICKEN_PROMPTS),
            ("goat",            GOAT_PROMPTS),
            ("quail",           QUAIL_PROMPTS),
            ("cow",             COW_PROMPTS),
        ]
        contexts = [
            "studio photography",
            "clean white background",
            "professional animal portrait",
            "wildlife photography style",
            "full body visible",
            "natural lighting",
        ]
        for subcat, items in all_animals:
            for item in items:
                for ctx in contexts:
                    p = self.make_animal_prompt(item, ctx)
                    prompts.append({"category": "poultry_animals",
                                    "subcategory": subcat,
                                    "prompt": p,
                                    "seed": random.randint(1, 999999)})
        return prompts

    # ── 2. RAW MEAT & EGGS ───────────────────────────────────
    def generate_raw_meat_prompts(self):
        prompts = []
        meat_style = [
            "butcher shop product photography",
            "fresh food photography",
            "commercial food photography",
            "studio food photography",
        ]
        all_meats = [
            ("raw_chicken", RAW_CHICKEN_PROMPTS),
            ("raw_goat",    RAW_GOAT_PROMPTS),
            ("raw_quail",   RAW_QUAIL_PROMPTS),
            ("eggs",        EGG_PROMPTS),
        ]
        for subcat, items in all_meats:
            for item in items:
                for style in meat_style:
                    angle = random.choice(CAMERA_ANGLES)
                    p = self.make_prompt(item, f"{style}, {angle}")
                    prompts.append({"category": "raw_meat",
                                    "subcategory": subcat,
                                    "prompt": p,
                                    "seed": random.randint(1, 999999)})
        return prompts

    # ── 3. VEHICLES ──────────────────────────────────────────
    def generate_vehicle_prompts(self):
        prompts = []
        car_details = [
            "clean polished bodywork",
            "studio automotive photography",
            "commercial vehicle photography",
            "showroom quality presentation",
            "professional car photography",
        ]
        for car_type, car_list in INDIAN_CAR_PROMPTS.items():
            for car in car_list:
                for detail in car_details:
                    p = self.make_prompt(car, detail)
                    prompts.append({"category": "vehicles",
                                    "subcategory": f"cars_{car_type}",
                                    "prompt": p,
                                    "seed": random.randint(1, 999999)})

        bike_details = [
            "shiny chrome detail visible",
            "studio motorcycle photography",
            "commercial bike photography",
            "showroom quality presentation",
            "professional bike photography",
        ]
        for bike_type, bike_list in BIKE_PROMPTS.items():
            for bike in bike_list:
                for detail in bike_details:
                    p = self.make_prompt(bike, detail)
                    prompts.append({"category": "vehicles",
                                    "subcategory": f"bikes_{bike_type}",
                                    "prompt": p,
                                    "seed": random.randint(1, 999999)})

        auto_details = [
            "clean painted bodywork",
            "studio vehicle photography",
            "commercial vehicle photography",
            "professional auto photography",
            "showroom presentation",
        ]
        for auto in AUTO_RICKSHAW_PROMPTS:
            for detail in auto_details:
                p = self.make_prompt(auto, detail)
                prompts.append({"category": "vehicles",
                                "subcategory": "auto_rickshaw",
                                "prompt": p,
                                "seed": random.randint(1, 999999)})
        return prompts

    # ── 4. FLOWERS ───────────────────────────────────────────
    def generate_flower_prompts(self):
        prompts = []
        photo = [
            "macro close-up photography",
            "botanical studio photography",
            "fine art floral photography",
            "natural light photography",
        ]
        for subcat, items in FLOWER_SINGLE_PROMPTS.items():
            for item in items:
                for ctx in FLOWER_CONTEXTS:
                    approach = random.choice(photo)
                    p = self.make_prompt(f"{item}, {ctx}", approach)
                    prompts.append({"category": "flowers",
                                    "subcategory": f"single_{subcat}",
                                    "prompt": p,
                                    "seed": random.randint(1, 999999)})

        for batch in FLOWER_GROUP_PROMPTS:
            for approach in photo:
                p = self.make_prompt(batch, approach)
                prompts.append({"category": "flowers",
                                "subcategory": "group_flowers",
                                "prompt": p,
                                "seed": random.randint(1, 999999)})
        return prompts

    # ── 5. FRUITS ────────────────────────────────────────────
    def generate_fruit_prompts(self):
        prompts = []
        photo = [
            "studio product photography",
            "overhead flat lay photography",
            "natural light photography",
            "editorial food photography",
        ]
        for subcat, items in FRUIT_SINGLE_PROMPTS.items():
            for item in items:
                for ctx in FRUIT_CONTEXTS:
                    p = self.make_prompt(f"{item}, {ctx}")
                    prompts.append({"category": "fruits",
                                    "subcategory": f"single_{subcat}",
                                    "prompt": p,
                                    "seed": random.randint(1, 999999)})

        for batch in FRUIT_GROUP_PROMPTS:
            for style in photo:
                p = self.make_prompt(batch, style)
                prompts.append({"category": "fruits",
                                "subcategory": "group_fruits",
                                "prompt": p,
                                "seed": random.randint(1, 999999)})
        return prompts

    # ── 6. VEGETABLES ────────────────────────────────────────
    def generate_vegetable_prompts(self):
        prompts = []
        photo = [
            "studio product photography",
            "overhead flat lay photography",
            "natural light photography",
            "editorial food photography",
        ]
        for subcat, items in VEG_SINGLE_PROMPTS.items():
            for item in items:
                for ctx in VEG_CONTEXTS:
                    p = self.make_prompt(f"{item}, {ctx}")
                    prompts.append({"category": "vegetables",
                                    "subcategory": f"single_{subcat}",
                                    "prompt": p,
                                    "seed": random.randint(1, 999999)})

        for batch in VEG_GROUP_PROMPTS:
            for style in photo:
                p = self.make_prompt(batch, style)
                prompts.append({"category": "vegetables",
                                "subcategory": "group_vegetables",
                                "prompt": p,
                                "seed": random.randint(1, 999999)})
        return prompts

    # ── 7. COOL DRINKS ───────────────────────────────────────
    def generate_drink_prompts(self):
        prompts = []
        for subcat, items in DRINK_PROMPTS.items():
            for item in items:
                for vessel in DRINK_VESSELS:
                    detail = random.choice(DRINK_DETAILS)
                    p = self.make_prompt(f"{item}", f"{vessel}, {detail}, beverage photography")
                    prompts.append({"category": "cool_drinks",
                                    "subcategory": subcat,
                                    "prompt": p,
                                    "seed": random.randint(1, 999999)})
        return prompts

    # ── 8. INDIAN FOODS ──────────────────────────────────────
    def generate_indian_food_prompts(self):
        prompts = []
        for subcat, items in INDIAN_FOOD_PROMPTS.items():
            for item in items:
                for vessel in INDIAN_FOOD_VESSELS:
                    angle = random.choice(FOOD_ANGLES)
                    p = self.make_prompt(f"{item}, {vessel}", f"{angle}, food photography")
                    prompts.append({"category": "indian_foods",
                                    "subcategory": subcat,
                                    "prompt": p,
                                    "seed": random.randint(1, 999999)})
        return prompts

    # ── 9. WORLD FOODS ───────────────────────────────────────
    def generate_world_food_prompts(self):
        prompts = []
        for subcat, items in WORLD_FOOD_PROMPTS.items():
            for item in items:
                for vessel in WORLD_FOOD_VESSELS:
                    angle = random.choice(FOOD_ANGLES)
                    p = self.make_prompt(f"{item}, {vessel}", f"{angle}, food photography")
                    prompts.append({"category": "world_foods",
                                    "subcategory": subcat,
                                    "prompt": p,
                                    "seed": random.randint(1, 999999)})
        return prompts

    # ── 10. FOOTWEAR ─────────────────────────────────────────
    def generate_footwear_prompts(self):
        prompts = []
        details = [
            "product photography",
            "studio footwear photography",
            "commercial shoe photography",
            "clean white surface",
            "professional product shot",
        ]
        for subcat, items in FOOTWEAR_PROMPTS.items():
            for item in items:
                for view in SHOE_VIEWS:
                    detail = random.choice(details)
                    p = self.make_prompt(f"{item}, {view}", detail)
                    prompts.append({"category": "footwear",
                                    "subcategory": subcat,
                                    "prompt": p,
                                    "seed": random.randint(1, 999999)})
        return prompts

    # ── 11. INDIAN DRESS ─────────────────────────────────────
    def generate_dress_prompts(self):
        prompts = []
        styles = [
            "fashion product photography",
            "textile studio photography",
            "ethnic wear catalog photography",
            "flat lay fashion photography",
        ]
        for subcat, items in DRESS_PROMPTS.items():
            for item in items:
                for ctx in DRESS_CONTEXTS:
                    style = random.choice(styles)
                    p = self.make_prompt(f"{item}, {ctx}", style)
                    prompts.append({"category": "indian_dress",
                                    "subcategory": subcat,
                                    "prompt": p,
                                    "seed": random.randint(1, 999999)})
        return prompts

    # ── 12. JEWELLERY MODELS ─────────────────────────────────
    def generate_jewellery_model_prompts(self):
        prompts = []
        for subcat, items in JEWELLERY_MODEL_PROMPTS.items():
            for item in items:
                for look in MODEL_LOOKS:
                    saree = random.choice(MODEL_SAREE)
                    p = self.make_model_prompt(f"{item}, {saree}, {look}")
                    prompts.append({"category": "jewellery_models",
                                    "subcategory": subcat,
                                    "prompt": p,
                                    "seed": random.randint(1, 999999)})
        return prompts

    # ── 13. OFFICE MODELS ────────────────────────────────────
    def generate_office_model_prompts(self):
        prompts = []
        for subcat, items in OFFICE_MODEL_PROMPTS.items():
            for item in items:
                for pose in MODEL_POSES_OFFICE:
                    p = self.make_model_prompt(f"{item}, {pose}")
                    prompts.append({"category": "office_models",
                                    "subcategory": subcat,
                                    "prompt": p,
                                    "seed": random.randint(1, 999999)})
        return prompts

    # ═══════════════════════════════════════════════════════════
    # GENERATE ALL
    # ═══════════════════════════════════════════════════════════

    def generate_all_prompts(self):
        print("🎨 Guru Image Usha — PNG Library V4")
        print("=" * 60)
        all_prompts = []

        generators = [
            ("Live Poultry & Animals",   self.generate_poultry_animal_prompts),
            ("Raw Meat & Eggs",          self.generate_raw_meat_prompts),
            ("Vehicles",                 self.generate_vehicle_prompts),
            ("Flowers",                  self.generate_flower_prompts),
            ("Fruits",                   self.generate_fruit_prompts),
            ("Vegetables",               self.generate_vegetable_prompts),
            ("Cool Drinks",              self.generate_drink_prompts),
            ("Indian Foods",             self.generate_indian_food_prompts),
            ("World Foods",              self.generate_world_food_prompts),
            ("Footwear",                 self.generate_footwear_prompts),
            ("Indian Dress",             self.generate_dress_prompts),
            ("Jewellery Models",         self.generate_jewellery_model_prompts),
            ("Office Models",            self.generate_office_model_prompts),
        ]

        counts = {}
        for name, fn in generators:
            prev = len(all_prompts)
            all_prompts.extend(fn())
            cnt = len(all_prompts) - prev
            counts[name] = cnt
            print(f"  ✅ {name}: {cnt}")

        # Seed multiplier — each prompt × 2
        variations = [
            "extremely detailed surface texture",
            "ultra sharp focus",
            "crisp clean photographic quality",
            "true to life rendering",
            "lifelike realistic detail",
            "fine grain detail visible",
        ]
        extended = []
        for item in all_prompts:
            extended.append(item)
            copy = dict(item)
            copy["prompt"] = item["prompt"] + f", {random.choice(variations)}"
            copy["seed"]   = random.randint(100000, 999999)
            extended.append(copy)
        all_prompts = extended

        print(f"\n  🔁 Seed multiplier: {len(all_prompts)} total prompts")
        random.shuffle(all_prompts)

        for i, p in enumerate(all_prompts):
            p["index"]    = i
            p["filename"] = f"img_{i:06d}.png"
            p["status"]   = "pending"

        print(f"\n🎯 TOTAL: {len(all_prompts)} prompts")
        print("\n📊 Summary:")
        for name, cnt in counts.items():
            print(f"   {name:35s}: {cnt:5d} base → {cnt*2:5d} total")

        return all_prompts

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
            size_kb = fpath.stat().st_size / 1024
            print(f"  💾 {cat}.json → {len(items)} prompts ({size_kb:.0f} KB)")

        index = {
            "total": len(prompts),
            "categories": list(by_cat.keys()),
            "files": [f"{c}.json" for c in by_cat],
        }
        with open(out / "index.json", "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2, ensure_ascii=False)

        print(f"\n✅ Saved {len(prompts)} prompts → {len(by_cat)} categories in '{output_dir}/'")
        return output_dir


def load_all_prompts(splits_dir="prompts/splits"):
    splits     = Path(splits_dir)
    index_file = splits / "index.json"

    if index_file.exists():
        index = json.loads(index_file.read_text())
        files = [splits / f for f in index["files"]]
    else:
        files = sorted(splits.glob("*.json"))
        files = [f for f in files if f.name != "index.json"]

    all_prompts = []
    for fpath in files:
        with open(fpath, encoding="utf-8") as f:
            all_prompts.extend(json.load(f))

    print(f"📦 Loaded {len(all_prompts)} prompts from {len(files)} files.")
    return all_prompts


if __name__ == "__main__":
    engine = PromptEngine()
    engine.save_prompts("prompts/splits")
