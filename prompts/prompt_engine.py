"""
PNG Library - Prompt Engine V3
=======================================================
V3 Changes:
  - Content-based filename (never regenerate same image)
  - Priority order: Indian animals -> Food -> Raw meat ->
    Vegetables -> Fruits -> Flowers -> rest
  - Animals: Sea removed, Wild = Lion/Tiger/Cheetah only
  - Added: Broiler, Rooster, Quail, Desi dog, Edible fish,
           Eggs, Raw Chicken/Mutton/Fish/Prawn meat
  - Added: 15+ Indian vegetables (Sorakkai, Pudalai, etc.)
  - Added: 8+ Indian fruits (Sapota, Nelli, Nongu, etc.)
  - All Indian food items complete
=======================================================
"""

import random
import json
import hashlib
import re
from pathlib import Path

# ─────────────────────────────────────────────
# MASTER PROMPT FORMULA
# ─────────────────────────────────────────────

BASE_SUFFIX = (
    "isolated on solid light grey background, "
    "professional studio product photography, "
    "shot on Canon EOS R5 with 100mm macro lens, "
    "8k ultra high definition, photorealistic, "
    "razor sharp focus, studio strobe lighting with softbox, "
    "clean crisp edges, no shadows on background, centered composition"
)

VECTOR_SUFFIX = (
    "isolated on solid light grey background, "
    "clean vector graphic design, bold sharp typography, "
    "professional graphic design, high contrast, "
    "crisp clean edges, 8k resolution, print ready quality"
)

CAMERA_ANGLES = [
    "front view", "45 degree angle view", "top-down flat lay view",
    "side profile view", "3/4 perspective view", "close-up macro shot",
    "low angle heroic view", "eye level straight on view"
]

LIGHTING_STYLES = [
    "soft diffused studio strobe", "dramatic Rembrandt side lighting",
    "bright even fill lighting", "warm key light with cool fill",
    "high key bright studio lighting", "rim light with soft fill"
]

DETAIL_QUALITY = [
    "intricate surface texture visible", "ultra fine material detail",
    "every pore and grain visible", "lifelike realistic texture",
    "tactile surface quality", "true-to-life material rendering"
]

PHOTO_STYLES = [
    "commercial product photography", "editorial magazine photography",
    "studio catalog photography", "high-end advertising photography"
]

# ─────────────────────────────────────────────
# ANIMALS
# ─────────────────────────────────────────────

ANIMALS = {
    "farm": [
        "white broiler chicken full body standing",
        "brown desi country chicken naatu kozhi standing",
        "colorful Indian rooster cock with red comb standing proud",
        "small brown quail bird kadai standing",
        "white Pekin duck standing alert",
        "white turkey bird full body",
        "Indian white cow with hump standing",
        "Indian desi red Gir cow standing",
        "black water buffalo with curved horns standing",
        "brown and white goat with beard standing",
        "black Indian goat standing",
        "fluffy white sheep woolly coat standing",
        "brown lamb baby sheep standing",
        "Indian pig domestic standing",
        "Indian street dog desi dog standing alert",
        "golden retriever dog happy portrait",
        "Indian Rajapalayam white dog standing",
        "fresh whole Rohu fish Indian carp on surface",
        "fresh whole Catla fish big on surface",
        "fresh whole Tilapia fish on surface",
        "fresh whole Sardine fish mathi bunch",
        "fresh whole Mackerel fish ayalai on surface",
        "fresh whole Pomfret white fish on surface",
        "fresh whole Seer fish vanjaram steak cut",
        "fresh whole Snapper red fish on surface",
        "fresh raw prawns iraaal pile on surface",
        "fresh raw crab nandu on surface",
        "fresh raw squid on surface",
    ],
    "wild": [
        "male lion with full golden mane roaring",
        "Bengal tiger orange with black stripes walking",
        "cheetah spotted standing alert on rock",
    ],
    "pets": [
        "white Persian cat fluffy sitting",
        "white fluffy rabbit sitting upright",
        "Indian ringneck parakeet green perched",
    ],
}

# ─────────────────────────────────────────────
# RAW MEAT & EGGS
# ─────────────────────────────────────────────

RAW_MEAT = {
    "raw_chicken": [
        "whole raw broiler chicken cleaned on white surface",
        "raw chicken leg piece thighs and drumstick",
        "raw chicken breast fillet boneless",
        "raw chicken wings pair",
        "raw chicken curry cut pieces mixed",
        "raw chicken liver pieces fresh",
        "minced raw chicken keema in bowl",
    ],
    "raw_mutton": [
        "fresh raw goat mutton curry cut bone-in pieces",
        "raw mutton leg whole on surface",
        "raw mutton chops bone-in",
        "raw mutton ribs rack",
        "raw mutton keema minced in bowl",
        "raw mutton liver fresh pieces",
        "raw mutton kidney pair fresh",
    ],
    "raw_fish_seafood": [
        "fresh raw fish fillets vanjaram seer fish on tray",
        "raw prawn peeled deveined pile",
        "raw whole prawns with shell on tray",
        "raw crab cleaned halved on surface",
        "raw fish steak cross section cut",
        "raw squid rings on tray",
    ],
    "eggs": [
        "white chicken eggs pile on surface",
        "brown country eggs naatu muttai pile",
        "single white egg isolated",
        "cracked raw egg open yolk visible on surface",
        "dozen eggs in egg tray carton",
        "six brown country eggs in small basket",
        "small quail eggs kadai muttai pile spotted",
        "half boiled egg cut cross section yolk runny",
        "hard boiled egg peeled white",
        "fried egg sunny side up on pan",
        "scrambled eggs fluffy in pan",
        "omelette folded golden on pan",
    ],
}

# ─────────────────────────────────────────────
# INDIAN FOOD
# ─────────────────────────────────────────────

INDIAN_FOOD = {
    "biryani": {
        "types": [
            "Hyderabadi dum biryani with leg piece",
            "Lucknowi awadhi biryani",
            "Kolkata chicken biryani with potato",
            "Malabar biryani with coconut",
            "Dindigul thalappakatti biryani",
            "Ambur star biryani",
            "Thalassery biryani with cashews",
            "Chettinad biryani pepper spicy",
            "Mutton dum biryani bone-in pieces",
            "Prawn biryani with whole prawns",
            "Fish biryani Malabar style",
            "Egg biryani with boiled eggs",
            "Veg biryani with mixed vegetables",
        ],
        "vessels": ["deep ceramic bowl", "traditional copper handi pot",
                    "fresh banana leaf plate", "round steel plate thali",
                    "rustic clay pot", "engraved silver thali"],
        "garnish": ["topped with fresh mint leaves and fried onions",
                    "garnished with saffron strands and cashews",
                    "with boiled egg half and lemon wedge",
                    "with raita bowl and pickle on side"],
        "style": ["fine dining restaurant plating", "authentic home style serving",
                  "bustling street food style", "grand wedding feast presentation"],
    },
    "dosa": {
        "types": [
            "golden crispy masala dosa with potato filling",
            "paper thin ghee roast dosa",
            "fluffy set dosa stack",
            "green pesarattu dosa",
            "lacy rava dosa with onions",
            "delicate neer dosa translucent",
            "spicy egg dosa with fried egg",
            "cheese burst dosa",
            "butter ghee roast dosa crispy",
            "stuffed paneer dosa golden brown",
            "chicken dosa stuffed",
            "onion uttapam thick with toppings",
        ],
        "vessels": ["round stainless steel plate", "fresh green banana leaf",
                    "white ceramic dinner plate", "rustic wooden serving board"],
        "garnish": ["with white coconut chutney and sambar bowl",
                    "with red tomato chutney and green chutney",
                    "with melting butter pat on top",
                    "with gunpowder podi and sesame oil"],
        "style": ["South Indian breakfast style", "restaurant tiffin style",
                  "street food cart style", "traditional temple food style"],
    },
    "curry": {
        "types": [
            "rich creamy butter chicken",
            "vibrant green palak paneer",
            "thick dark dal makhani",
            "spicy chole masala with whole chickpeas",
            "Kerala fish curry in coconut gravy",
            "tender mutton rogan josh",
            "prawn masala in red gravy",
            "rajma kidney bean curry",
            "matar paneer with green peas",
            "smoky kadai chicken",
            "fiery Chettinad chicken curry",
            "tangy Goan fish curry",
            "egg masala curry with boiled eggs",
            "pepper chicken dry fry",
            "Chettinad mutton kuzhambu",
            "Tamil fish kuzhambu tamarind base",
            "chicken chettinad dry masala",
            "naatu kozhi country chicken curry",
            "Kerala prawn coconut curry",
            "chicken tikka masala creamy",
            "keema matar minced meat peas",
            "dal tadka yellow lentil",
            "sambar South Indian lentil vegetable",
        ],
        "vessels": ["glazed ceramic bowl", "hammered copper serving bowl",
                    "rustic clay pot", "deep stainless steel bowl", "white porcelain bowl"],
        "garnish": ["with fresh coriander leaves on top", "with cream swirl drizzle",
                    "served with hot naan bread on side", "with steaming jeera rice",
                    "with lime pickle and papadum on side"],
        "style": ["restaurant fine dining plating", "home kitchen style", "traditional thali style serving"],
    },
    "rice": {
        "types": [
            "steaming white basmati rice in bowl",
            "lemon rice with mustard seeds and curry leaves",
            "tomato rice South Indian style",
            "tamarind rice puliyodharai mixed",
            "coconut rice with fried cashews",
            "curd rice with pomegranate",
            "pongal rice with ghee and pepper",
            "bisi bele bath Karnataka style",
            "sambar rice mixed with sambar",
        ],
        "vessels": ["round stainless steel plate", "banana leaf", "white ceramic bowl"],
        "garnish": ["with pickle and papadum", "with ghee drizzle on top",
                    "with fried cashews and curry leaves"],
        "style": ["home style", "restaurant style", "thali style"],
    },
    "sweets": {
        "types": [
            "syrup soaked gulab jamun",
            "soft white rasgulla",
            "crispy orange jalebi",
            "round besan ladoo",
            "silver topped kaju barfi",
            "creamy rice kheer",
            "rich gajar ka halwa",
            "ghee dripping mysore pak",
            "motichoor ladoo textured",
            "diamond cut kaju katli",
            "aromatic rava kesari saffron orange",
            "creamy semiya payasam vermicelli",
            "sweet pongal sakkarai pongal",
            "coconut burfi white sweet",
            "peanut chikki candy bar",
            "adhirasam dark fried Tamil sweet",
            "kozhukattai modak steamed",
            "suzhiyam deep fried sweet ball",
            "halwa dark rich semolina",
            "malpua sweet pancake syrup soaked",
        ],
        "vessels": ["polished silver plate", "traditional brass plate",
                    "white ceramic dessert plate", "small clay cup kulhad",
                    "decorative mithai box", "fresh banana leaf"],
        "garnish": ["with edible silver vark on top", "with chopped pistachio garnish",
                    "with dried rose petals", "with saffron strands"],
        "style": ["festive celebration presentation", "sweet shop display style", "homemade rustic style"],
    },
    "snacks": {
        "types": [
            "crispy golden samosa",
            "crunchy medu vada",
            "spicy pani puri golgappa",
            "stuffed aloo tikki",
            "hot onion bhaji pakora",
            "flaky kachori",
            "tangy bhel puri",
            "crispy murukku spiral",
            "masala vada",
            "bread pakora stuffed",
            "dahi vada with curd",
            "crispy mixture namkeen",
            "ribbon pakoda crispy",
            "thattai crispy disc",
            "seedai fried rice ball",
            "boondhi crispy small balls",
            "banana chips Kerala crispy",
            "jackfruit chips crispy",
            "tapioca chips kappa chips",
            "pav bhaji with butter",
            "aloo chaat tangy",
            "corn chaat spicy",
            "panipuri chaat platter",
        ],
        "vessels": ["newspaper cone", "steel plate", "ceramic bowl",
                    "banana leaf", "paper plate", "wire basket"],
        "garnish": ["with green mint chutney", "with tamarind chutney drizzle",
                    "with sliced onion rings and lemon", "with sev and coriander topping"],
        "style": ["street food style", "restaurant appetizer style", "tea time snack style"],
    },
    "bread": {
        "types": [
            "puffed hot tandoori naan",
            "layered flaky parotta",
            "whole wheat chapati",
            "crispy golden puri",
            "stuffed aloo paratha",
            "thick roomali roti",
            "garlic butter naan",
            "kulcha amritsari stuffed",
            "bhatura puffed",
            "appam Kerala lacy white",
            "idiyappam string hopper white",
            "poori masala puffed",
            "veechu parotta flaky layers",
        ],
        "vessels": ["wicker basket lined with cloth", "steel plate", "wooden board", "banana leaf"],
        "garnish": ["with butter melting on top", "with coriander sprinkle", "with pickle and curd on side"],
        "style": ["tandoor fresh style", "home kitchen style", "dhaba style"],
    },
    "idli_sambar": {
        "types": [
            "soft white idli stack on plate",
            "mini idli small pieces",
            "rava idli semolina soft",
            "idli with sambar and chutneys",
            "steaming hot sambar in bowl",
            "thick tomato sambar",
            "mixed vegetable sambar",
            "drumstick sambar with drumsticks",
            "rasam thin pepper soup",
            "filter coffee South Indian davara set",
        ],
        "vessels": ["stainless steel plate", "banana leaf", "ceramic plate"],
        "garnish": ["with coconut chutney", "with sambar poured over", "with ghee drizzle"],
        "style": ["South Indian breakfast style", "tiffin center style"],
    },
    "non_veg_dishes": {
        "types": [
            "chicken 65 deep fried spicy",
            "tandoori chicken half grilled",
            "chicken tikka grilled skewer",
            "mutton kebab seekh grilled",
            "fish fry South Indian crispy",
            "prawn fry masala dry",
            "crab masala dry with shells",
            "chicken lollipop fried",
            "egg bhurji scrambled spicy",
            "chicken shawarma roll wrap",
            "fish fingers crispy",
            "chicken malai tikka creamy",
            "squid fry crispy rings",
            "lobster masala spicy",
        ],
        "vessels": ["steel plate", "white ceramic plate", "wooden board", "banana leaf"],
        "garnish": ["with onion rings and lemon", "with mint chutney", "with sliced green chili"],
        "style": ["restaurant style", "street food style", "tandoor style"],
    },
    "thali": {
        "types": [
            "full South Indian vegetarian thali complete",
            "North Indian thali with dal roti paneer",
            "Tamil Nadu thali on banana leaf",
            "Kerala sadya full banana leaf meal",
            "full non-veg thali with chicken mutton",
            "Gujarati thali sweet and savory",
        ],
        "vessels": ["large stainless steel thali plate", "banana leaf", "traditional brass thali"],
        "garnish": ["with all items arranged", "fully loaded with rice curry sides"],
        "style": ["restaurant thali style", "wedding feast style", "traditional home style"],
    },
}

WORLD_FOOD = {
    "pizza": [
        "thin crust Margherita pizza with fresh basil",
        "deep dish pepperoni pizza with melted cheese pull",
        "loaded BBQ chicken pizza",
        "four cheese pizza melted",
    ],
    "burger": [
        "juicy beef cheeseburger with melting cheddar",
        "crispy fried chicken burger with coleslaw",
        "smash burger with caramelized onions",
    ],
    "sushi": [
        "fresh salmon nigiri sushi glistening",
        "colorful maki sushi platter assorted",
        "California roll with avocado and crab",
    ],
    "pasta": [
        "creamy spaghetti carbonara with egg yolk",
        "rich fettuccine alfredo with parmesan",
        "spicy penne arrabbiata with chili flakes",
    ],
    "chinese": [
        "steaming dim sum bamboo basket",
        "crispy spring rolls golden brown",
        "orange chicken with sesame seeds",
    ],
    "desserts_world": [
        "molten chocolate lava cake oozing",
        "creamy strawberry cheesecake slice",
        "classic tiramisu with cocoa dusting",
        "colorful French macaron stack",
    ],
}

# ─────────────────────────────────────────────
# VEGETABLES
# ─────────────────────────────────────────────

VEGETABLES = {
    "leafy": [
        "fresh spinach bunch",
        "green lettuce head crisp",
        "cabbage head green round",
        "curry leaves branch fresh green",
        "fenugreek leaves vendhaya keerai bunch",
        "amaranth leaves mulai keerai bunch",
        "drumstick leaves murungai keerai bunch",
        "fresh methi fenugreek leaves bunch",
        "agathi keerai white flower leaves bunch",
    ],
    "root": [
        "fresh carrots bunch with tops",
        "red beetroot whole and sliced",
        "ginger root knobby fresh",
        "turmeric root fresh yellow",
        "radish white daikon long",
        "radish red round",
        "sweet potato orange flesh",
        "potato russet brown whole",
        "onion red halved rings visible",
        "onion white whole",
        "shallots small sambar onion bunch",
        "garlic bulb whole and cloves",
        "garlic peeled cloves pile",
        "yam senaikizhangu whole and cut",
        "purple yam karunai kizhangu whole",
        "colacasia root seppankizhangu pile",
        "elephant foot yam karunaikizhangu cut",
        "tapioca root kappa maravalli whole",
    ],
    "gourds": [
        "bottle gourd sorakkai whole green long",
        "ash gourd venpusani whole pale green large",
        "ridge gourd peerkan whole ribbed green",
        "snake gourd pudalangai long white green",
        "bitter gourd pavakkai whole textured green",
        "ivy gourd kovakkai small red green",
        "spine gourd kantola small spiky",
        "pointed gourd parwal small oval green",
    ],
    "cooking": [
        "red tomato vine ripe",
        "green bell pepper glossy",
        "red chili peppers bunch",
        "green chili peppers bunch",
        "dry red chili whole",
        "eggplant brinjal purple glossy",
        "small green brinjal kathirikkai bunch",
        "okra ladyfinger green whole",
        "drumstick moringa long pod",
        "green beans french fresh",
        "cauliflower head white",
        "broccoli head green florets",
        "cluster beans kothavarai bunch",
        "peas in pod fresh green",
        "green peas shelled fresh",
        "raw banana vazhakkai green unripe",
        "raw jackfruit palakkai cut green",
        "raw papaya green whole",
        "banana flower valaipoo purple",
        "raw mango mangai green sour",
        "turkey berry sundakkai small bunch",
    ],
    "exotic": [
        "mushroom button white fresh",
        "mushroom oyster cluster",
        "corn on cob yellow kernels",
        "avocado halved with pit",
        "baby corn bunch yellow",
        "zucchini green",
    ],
}

# ─────────────────────────────────────────────
# FRUITS
# ─────────────────────────────────────────────

FRUITS = {
    "tropical_indian": [
        "ripe golden Alphonso mango whole and sliced",
        "ripe Banganapalli mango yellow",
        "green raw mango mangai sour",
        "fresh pineapple with crown",
        "split open coconut with water",
        "ripe papaya half with seeds",
        "bunch of yellow bananas",
        "small red banana sevvazhai bunch",
        "dragon fruit halved pink flesh",
        "rambutan cluster red hairy",
        "jackfruit whole and opened",
        "guava cut green pink flesh",
        "sapota chickoo brown soft ripe",
        "custard apple seetha pazham green ripe",
        "amla Indian gooseberry nellikai green small pile",
        "wood apple vilampazham round brown",
        "palmyra palm fruit nongu jelly white",
        "tamarind pod puli brown with seeds",
        "star fruit kamrakh yellow sliced",
        "bael vilvam stone fruit whole cracked",
        "passion fruit cut open",
        "lychee cluster red",
        "longan fruit cluster",
    ],
    "citrus": [
        "orange sliced cross section juicy",
        "lemon whole and halved",
        "lime green fresh",
        "grapefruit pink halved",
        "tangerine peeled segments",
        "sweet lime mosambi whole and halved",
        "kinnow mandarin orange",
    ],
    "berries": [
        "fresh red strawberries in heap",
        "plump blueberries cluster",
        "Indian blackberry jamun dark purple pile",
        "amla gooseberry green pile",
        "karonda berry small red",
    ],
    "common": [
        "red apple shiny with water droplets",
        "green apple Granny Smith",
        "green pear ripe",
        "purple grapes bunch on vine",
        "green seedless grapes bunch",
        "watermelon slice triangular",
        "watermelon whole round green",
        "pomegranate cut open red seeds",
        "peach fuzzy skin",
        "plum dark purple",
        "kiwi halved green flesh",
        "fig cut open revealing inside",
        "cherries pair with stem",
        "muskmelon cantaloupe orange flesh halved",
    ],
}

# ─────────────────────────────────────────────
# FLOWERS
# ─────────────────────────────────────────────

FLOWERS = {
    "rose": [
        "deep red velvet rose", "soft pink garden rose", "pure white rose",
        "bright yellow rose", "sunset orange rose", "royal purple rose",
        "peach blush rose", "dark burgundy rose",
    ],
    "lotus": [
        "pink lotus flower in bloom", "pure white lotus open",
        "purple lotus with golden center", "red lotus bud opening",
    ],
    "jasmine": [
        "white jasmine flower cluster", "arabian jasmine buds",
        "jasmine garland string fresh", "jasmine buds and blooms mixed",
    ],
    "sunflower": [
        "large yellow sunflower head with seeds visible",
        "sunflower bouquet three stems", "sunflower fully open face",
    ],
    "orchid": [
        "purple phalaenopsis orchid spray", "white dendrobium orchid stem",
        "pink cymbidium orchid bloom",
    ],
    "marigold": [
        "deep orange marigold full bloom", "bright yellow marigold round",
        "marigold garland thick fresh", "marigold bunch tied",
    ],
    "lily": [
        "elegant white calla lily", "spotted orange tiger lily",
        "fragrant pink stargazer lily", "white Easter lily trumpet",
    ],
    "hibiscus": [
        "bright red hibiscus with yellow stamen", "yellow hibiscus tropical",
        "pink double hibiscus", "white hibiscus delicate",
    ],
    "other_flowers": [
        "cherry blossom branch pink", "lavender stems bunch purple",
        "dahlia flower multi-layered petals", "lush peony bloom soft pink",
        "tulip flower red single", "purple iris flower",
        "gerbera daisy bright orange", "red anthurium heart shaped",
        "crossandra kanakambaram orange garland flower",
        "chrysanthemum samandhi white yellow bloom",
    ],
}

FLOWER_STAGES = ["in full bloom petals open", "half open bud unfurling", "tight fresh bud"]
FLOWER_CONTEXT = [
    "single long stem", "small arranged bouquet",
    "with morning dewdrops on petals", "freshly cut with water droplets"
]

# ─────────────────────────────────────────────
# VEHICLES
# ─────────────────────────────────────────────

CARS = {
    "sports_car": [
        "red Ferrari 458 Italia", "yellow Lamborghini Huracan",
        "blue Porsche 911 GT3", "black Bugatti Chiron",
    ],
    "suv": [
        "black Range Rover Sport", "white Toyota Land Cruiser",
        "white Hyundai Creta 2024", "black Kia Seltos GTX",
        "red Mahindra Thar 4x4", "white Mahindra Scorpio N",
        "silver Tata Safari 2024", "white Toyota Fortuner",
    ],
    "sedan": [
        "white Toyota Camry hybrid", "blue BMW 3 Series M Sport",
        "red Hyundai Verna turbo", "white Maruti Dzire", "white Honda City",
    ],
    "hatchback": [
        "red Maruti Swift hatchback", "blue Hyundai i20",
        "white Tata Punch compact", "red Volkswagen Polo",
    ],
    "vintage": [
        "cherry red 1967 Ford Mustang GT",
        "baby blue 1957 Chevrolet Bel Air",
        "mint green 1963 Volkswagen Beetle",
    ],
    "electric": [
        "white Tesla Model S Plaid", "white Hyundai Ioniq 6",
        "Tata Nexon EV blue", "MG ZS EV white",
    ],
    "luxury": [
        "black Rolls Royce Ghost", "silver Mercedes S-Class Maybach",
        "dark blue Bentley Continental GT",
    ],
}

BIKES = {
    "sports_bike": [
        "red Honda CBR1000RR-R Fireblade", "blue Yamaha YZF-R1M",
        "orange KTM RC 390", "red Ducati Panigale V4",
    ],
    "cruiser": [
        "black Royal Enfield Classic 350 chrome",
        "orange Royal Enfield Meteor 350",
        "chrome Harley Davidson Fat Boy",
        "burgundy Royal Enfield Super Meteor 650",
    ],
    "adventure": [
        "orange KTM 390 Adventure",
        "blue Royal Enfield Himalayan 450",
        "silver BMW R 1250 GS Adventure",
    ],
    "scooter": [
        "white Honda Activa 6G", "blue TVS Jupiter 125",
        "red Vespa Primavera 150", "yellow Yamaha Fascino 125",
        "black TVS NTorq 125",
    ],
}

CAR_ANGLES = [
    "front 3/4 view showing grille and headlights",
    "side profile view full length",
    "dramatic front view symmetrical",
    "dynamic low angle hero shot",
]

# ─────────────────────────────────────────────
# TREES & NATURE
# ─────────────────────────────────────────────

TREES = {
    "fruit_trees": [
        "mango tree with ripe hanging fruits",
        "tall coconut palm with coconuts",
        "banana tree with fruit bunch",
        "papaya tree with green and ripe fruits",
        "guava tree with ready fruits",
        "lemon tree with yellow lemons",
        "jackfruit tree with large hanging jackfruits",
        "sapota chikku tree with fruits",
        "pomegranate tree with split red fruits",
    ],
    "tropical": [
        "tall coconut palm against sky",
        "banana plant cluster tropical",
        "thick bamboo grove tall",
        "ancient Indian banyan tree with aerial roots",
        "sacred peepal tree large",
        "neem tree with small leaves",
    ],
    "small_plants": [
        "echeveria succulent rosette",
        "aloe vera plant thick leaves",
        "golden money plant pothos",
        "tulsi holy basil plant in pot",
        "miniature bonsai tree aged",
        "peace lily with white spathe",
    ],
}

TREE_CONTEXT = [
    "full tree view showing roots to canopy",
    "with visible fruits or flowers",
    "lush green healthy canopy",
    "bark and trunk detail close-up",
]

# ─────────────────────────────────────────────
# POTS & VESSELS
# ─────────────────────────────────────────────

POTS_VESSELS = {
    "clay_pots": [
        "traditional red clay pot with texture",
        "terracotta water pot tall",
        "hand painted blue clay pot",
        "black clay cooking pot rustic",
    ],
    "metal_vessels": [
        "hammered shiny copper pot",
        "engraved brass lota round",
        "polished steel cooking vessel",
        "ornate silver milk pot",
        "antique patina bronze vessel",
        "seasoned iron kadai deep wok",
        "pressure cooker stainless steel",
    ],
    "decorative": [
        "blue and white Chinese porcelain vase",
        "hand painted floral ceramic pot",
        "ornate golden decorative urn",
        "cut crystal glass vase sparkling",
    ],
}

# ─────────────────────────────────────────────
# SMOKE & EFFECTS
# ─────────────────────────────────────────────

SMOKE_EFFECTS = {
    "smoke": [
        "wispy white smoke trail thin",
        "thick billowing smoke column grey",
        "elegant curling smoke tendrils",
        "dense theatrical fog bank",
    ],
    "colored_smoke": [
        "vibrant red smoke bomb cloud",
        "electric blue smoke burst",
        "neon green smoke plume",
        "royal purple smoke billow",
        "bright yellow smoke trail",
        "deep orange smoke explosion",
    ],
    "fire": [
        "realistic orange flame tongues",
        "intense blue gas flame",
        "single candle flame warm glow",
        "bright fire sparks burst scattering",
    ],
    "sparkle": [
        "golden sparkle particle burst",
        "silver glitter explosion scattered",
        "magical dust particles floating",
        "colorful confetti burst celebration",
    ],
}

# ─────────────────────────────────────────────
# SKY & CELESTIAL
# ─────────────────────────────────────────────

SKY_ELEMENTS = {
    "sun": [
        "bright radiant sun with light rays",
        "golden sunrise sun glowing",
        "warm setting sun orange red",
        "sun with dramatic god rays",
    ],
    "moon": [
        "full moon realistic cratered surface",
        "thin crescent moon glowing",
        "golden supermoon glowing large",
        "blood moon lunar eclipse red",
    ],
    "stars": [
        "bright gold five pointed star metallic",
        "shooting star with trail streak",
        "metallic 3D gold star shiny",
    ],
    "clouds": [
        "fluffy white cumulus cloud",
        "dark grey storm cumulonimbus cloud",
        "rainbow arching over white cloud",
        "golden cloud lit by sunrise",
    ],
    "weather": [
        "forked lightning bolt bright",
        "double rainbow arc vivid colors",
        "detailed ice snowflake crystal macro",
    ],
}

# ─────────────────────────────────────────────
# FRAMES & BORDERS
# ─────────────────────────────────────────────

FRAMES_BORDERS = {
    "wedding": [
        "ornate carved gold wedding frame",
        "floral wedding border with pink roses",
        "elegant pearl white wedding frame",
        "vintage gold filigree flourish frame",
        "romantic flower arch wedding frame",
    ],
    "festival": [
        "Diwali diya oil lamp border gold",
        "Christmas holly berry border green red",
        "Pongal kolam rangoli border",
        "New Year fireworks celebration frame",
        "Holi colorful powder splash border",
    ],
    "modern": [
        "minimalist thin gold line border",
        "geometric hexagonal pattern frame",
        "neon glow edge rectangular border",
        "rounded corner clean modern frame",
        "artistic brushstroke edge border",
    ],
    "nature": [
        "circular floral wreath frame",
        "tropical palm leaves corner border",
        "vine and wildflower winding border",
        "sunflower circle frame",
    ],
}

# ─────────────────────────────────────────────
# OFFER LOGOS
# ─────────────────────────────────────────────

OFFER_LOGOS = {
    "discount": [
        "50% OFF sale badge", "30% discount sticker circular",
        "20% OFF rounded badge", "FLAT 40% OFF rectangular label",
        "MEGA SALE starburst badge", "CLEARANCE SALE hanging tag",
        "SAVE 25% ribbon label",
    ],
    "buy_deals": [
        "BUY 1 GET 1 FREE badge", "BUY 2 GET 1 FREE sticker",
        "FREE GIFT with purchase badge", "COMBO OFFER deal seal",
    ],
    "special_offers": [
        "SPECIAL OFFER starburst shape", "LIMITED TIME OFFER badge urgent",
        "TODAY ONLY deal badge", "FLASH SALE lightning bolt badge",
        "BEST PRICE guarantee badge green", "HOT DEAL fire theme badge",
        "EXCLUSIVE OFFER gold seal",
    ],
    "quality": [
        "BEST SELLER gold badge award", "TOP RATED five star badge",
        "NEW ARRIVAL ribbon label", "TRENDING NOW fire badge",
        "PREMIUM QUALITY shield seal", "100% GENUINE stamp badge",
    ],
}

# ─────────────────────────────────────────────
# JEWELLERY
# ─────────────────────────────────────────────

JEWELLERY = {
    "necklace": [
        "heavy gold temple necklace with ruby pendant",
        "diamond solitaire pendant on thin chain",
        "classic pearl strand necklace lustrous",
        "ruby and gold traditional necklace",
        "bridal kundan necklace set elaborate",
        "oxidized silver tribal necklace",
    ],
    "earrings": [
        "gold jhumka bell earrings with pearls",
        "round diamond stud earrings sparkling",
        "pearl drop earrings on gold hooks",
        "chandbali gold earrings crescent shaped",
        "large gold hoop earrings polished",
    ],
    "rings": [
        "diamond solitaire engagement ring platinum",
        "plain gold band ring polished",
        "oval ruby ring in gold setting",
        "oxidized silver cocktail ring large",
    ],
    "bangles": [
        "set of gold bangles stacked",
        "colorful glass bangles Indian traditional",
        "thick silver bangle bracelet engraved",
        "bridal kundan bangle set ornate",
        "heavy gold kada bangle single",
    ],
}

# ─────────────────────────────────────────────
# SPICES
# ─────────────────────────────────────────────

SPICES = {
    "whole_spices": [
        "whole cinnamon sticks bundle",
        "green cardamom pods pile",
        "star anise whole dried",
        "whole cloves dried pile",
        "black peppercorns heap",
        "whole cumin seeds mound",
        "mustard seeds yellow and black",
        "fenugreek seeds pile",
        "dried red chili whole bunch",
        "bay leaves dried",
        "fennel seeds sombu pile",
    ],
    "ground_spices": [
        "bright turmeric powder mound",
        "red chili powder vibrant",
        "coriander powder golden brown",
        "cumin powder aromatic",
        "garam masala powder blend",
        "black pepper powder fresh ground",
        "Chettinad masala powder blend",
        "sambar powder blend",
        "rasam powder",
    ],
    "fresh_herbs": [
        "fresh coriander cilantro bunch",
        "fresh mint leaves bunch",
        "curry leaves on stem fresh",
        "fresh basil bunch green",
    ],
}

SPICE_CONTEXT = [
    "in small brass bowl", "on wooden spoon",
    "scattered on slate surface", "in glass jar open",
    "in traditional spice box compartment",
]

# ─────────────────────────────────────────────
# BEVERAGES
# ─────────────────────────────────────────────

BEVERAGES = {
    "hot_drinks": [
        "steaming cup of masala chai in glass cup",
        "latte art coffee in ceramic cup",
        "black coffee in white mug with steam",
        "green tea in glass cup clear",
        "hot chocolate with whipped cream and cocoa",
        "golden turmeric latte in mug",
    ],
    "cold_drinks": [
        "iced coffee with cream layered in tall glass",
        "fresh orange juice in glass with ice",
        "green smoothie in mason jar",
        "mango lassi in tall glass creamy",
        "rose milk falooda with ice cream",
        "fresh coconut water in tender coconut",
        "lemonade with mint leaves in pitcher",
    ],
    "traditional": [
        "filter coffee in brass davara tumbler set",
        "masala chai in terracotta kulhad cup",
        "jigarthanda cold drink in tall glass",
        "thandai with almond and saffron",
        "paneer soda pink in glass bottle",
        "buttermilk chaas in brass glass",
        "sugarcane juice in glass fresh",
    ],
}

# ─────────────────────────────────────────────
# SHOES
# ─────────────────────────────────────────────

SHOES = {
    "sneakers": [
        "white Nike Air Force 1 sneakers",
        "Adidas Ultraboost running shoes black",
        "Converse Chuck Taylor high top red",
        "minimalist white leather sneakers clean",
    ],
    "formal": [
        "black Oxford leather shoes polished",
        "brown Derby brogue shoes",
        "patent leather dress shoes shiny",
        "suede loafers tan",
    ],
    "traditional": [
        "brown leather kolhapuri chappal",
        "embroidered Rajasthani jutti colorful",
        "wooden paduka traditional",
    ],
    "boots": [
        "brown Chelsea boots leather",
        "black combat military boots",
        "hiking boots waterproof rugged",
    ],
    "sandals": [
        "leather gladiator sandals brown",
        "rubber flip flops colorful",
        "sports sandals with velcro straps",
    ],
}

# ─────────────────────────────────────────────
# BAGS
# ─────────────────────────────────────────────

BAGS = {
    "handbags": [
        "luxury leather tote bag tan",
        "quilted designer crossbody bag black",
        "structured satchel bag burgundy leather",
        "mini bucket bag red",
    ],
    "backpacks": [
        "hiking backpack with gear loops green",
        "leather backpack vintage brown",
        "modern laptop backpack grey slim",
        "canvas school backpack navy",
    ],
    "travel": [
        "hard shell suitcase large silver",
        "leather duffle bag brown",
        "cabin trolley bag compact black",
    ],
    "traditional": [
        "jute shopping bag printed",
        "cotton tote bag embroidered",
        "silk potli bag drawstring",
    ],
}

# ─────────────────────────────────────────────
# COSMETICS
# ─────────────────────────────────────────────

COSMETICS = {
    "makeup": [
        "red lipstick bullet open luxury gold case",
        "eyeshadow palette with mirror open",
        "mascara wand with product",
        "foundation bottle glass with pump",
        "compact powder with mirror and puff",
        "makeup brush set in holder",
    ],
    "skincare": [
        "glass serum bottle with dropper",
        "moisturizer cream jar open white",
        "face wash tube squeezed",
        "sunscreen bottle SPF label",
    ],
    "fragrance": [
        "luxury perfume bottle with gold cap",
        "cologne bottle masculine design",
        "attar perfume oil bottle traditional",
        "reed diffuser with sticks in glass bottle",
    ],
    "hair_care": [
        "shampoo bottle professional salon",
        "wooden hair brush boar bristle",
        "hair oil bottle with herbs visible",
    ],
}

# ─────────────────────────────────────────────
# SPORTS
# ─────────────────────────────────────────────

SPORTS = {
    "cricket": [
        "cricket bat willow wood with grip",
        "red cricket ball leather with seam",
        "cricket helmet with face guard",
        "cricket wicket stumps and bails set",
    ],
    "football": [
        "FIFA match football with panels",
        "football boots with studs",
        "goalkeeper gloves professional",
    ],
    "badminton_tennis": [
        "badminton racket with shuttlecock",
        "tennis racket with green ball",
        "badminton shuttlecock feather white",
    ],
    "fitness": [
        "pair of steel dumbbells heavy",
        "yoga mat rolled purple",
        "resistance bands set colored",
        "kettlebell cast iron black",
    ],
    "other_sports": [
        "basketball orange textured",
        "boxing gloves red leather laced",
        "swimming goggles with strap",
        "archery bow and arrow set",
    ],
}

# ─────────────────────────────────────────────
# MUSICAL INSTRUMENTS
# ─────────────────────────────────────────────

MUSICAL_INSTRUMENTS = {
    "string": [
        "acoustic guitar wood grain visible",
        "electric guitar sunburst finish",
        "classical violin with bow",
        "Indian sitar with resonator",
        "Indian veena traditional ornate",
        "cello full size wooden",
    ],
    "percussion": [
        "tabla pair Indian drums",
        "mridangam South Indian drum",
        "drum kit full set professional",
        "tambourine with jingles",
        "Indian dholak double headed",
    ],
    "wind": [
        "bamboo flute Indian bansuri",
        "saxophone golden brass",
        "trumpet polished brass",
        "clarinet black wooden",
        "shehnai Indian wedding instrument",
        "harmonica silver chrome",
    ],
    "keyboard": [
        "grand piano black glossy",
        "harmonium Indian keyboard bellows",
        "electronic keyboard synthesizer",
    ],
}

# ─────────────────────────────────────────────
# POOJA ITEMS
# ─────────────────────────────────────────────

POOJA_ITEMS = {
    "idols": [
        "brass Ganesha idol detailed",
        "marble Krishna playing flute idol",
        "bronze Nataraja Shiva dancing idol",
        "wooden Buddha meditating statue",
        "brass Lakshmi idol standing on lotus",
        "stone carved Hanuman idol",
        "panchaloha Saraswati idol with veena",
    ],
    "pooja_vessels": [
        "brass pooja thali with items complete",
        "copper kalash water pot with coconut",
        "silver kumkum box small ornate",
        "brass deepam oil lamp with wick",
        "bronze bell with handle pooja",
        "brass incense holder agarbatti stand",
        "silver camphor plate aarti",
    ],
    "garlands": [
        "fresh jasmine flower garland maalai long",
        "rose petal garland red and pink",
        "marigold and jasmine mixed garland thick",
        "tulsi holy basil mala beads",
        "rudraksha bead mala prayer",
    ],
    "accessories": [
        "sandalwood paste on stone grinder",
        "kumkum red powder in brass box",
        "agarbathi incense sticks bundle",
        "camphor tablets white on brass plate",
        "coconut whole with turmeric and flowers",
    ],
}

# ─────────────────────────────────────────────
# CLOTHING
# ─────────────────────────────────────────────

CLOTHING = {
    "indian_traditional": [
        "folded Kanchipuram silk saree gold border",
        "Banarasi silk saree rich brocade",
        "white Kerala kasavu mundu and veshti",
        "colorful Rajasthani bandhani dupatta",
        "embroidered Lucknowi chikankari kurta white",
        "Mysore silk saree folded with pallu visible",
    ],
    "mens_wear": [
        "crisp white formal dress shirt folded",
        "navy blue blazer jacket on hanger",
        "black leather belt coiled",
        "silk necktie rolled assorted colors",
        "denim jeans folded stack blue",
    ],
    "accessories": [
        "silk scarf folded elegant",
        "woolen shawl Kashmiri embroidered",
        "leather wallet brown open",
        "aviator sunglasses gold frame on surface",
    ],
}

# ─────────────────────────────────────────────
# MEDICAL
# ─────────────────────────────────────────────

MEDICAL = {
    "equipment": [
        "stethoscope silver on surface",
        "digital blood pressure monitor",
        "clinical thermometer digital",
        "first aid kit box red cross open",
    ],
    "supplies": [
        "syringe with needle medical",
        "medicine pill capsule assorted colors",
        "bandage roll white cotton",
        "face mask surgical blue disposable",
        "medicine bottle amber with label",
    ],
    "ayurveda": [
        "mortar and pestle with herbs ayurvedic",
        "neem leaves and powder",
        "turmeric root and powder golden",
        "ashwagandha root dried",
    ],
}

# ─────────────────────────────────────────────
# STATIONERY
# ─────────────────────────────────────────────

STATIONERY = {
    "writing": [
        "fountain pen with gold nib",
        "mechanical pencil with lead",
        "set of colored pencils in row",
        "ballpoint pen set luxury",
    ],
    "desk": [
        "leather bound notebook closed",
        "spiral notebook open blank pages",
        "desk organizer wooden with supplies",
        "tape dispenser and scissors set",
    ],
    "art_supplies": [
        "watercolor paint palette with brushes",
        "acrylic paint tubes assorted colors",
        "sketch pad with charcoal pencils",
    ],
}

# ─────────────────────────────────────────────
# ELECTRONICS
# ─────────────────────────────────────────────

ELECTRONICS = {
    "phones": [
        "latest iPhone Pro with triple camera system",
        "Samsung Galaxy S Ultra flagship phone",
        "OnePlus flagship phone sleek black",
    ],
    "laptops": [
        "MacBook Pro silver open showing screen",
        "gaming laptop with RGB keyboard glowing",
        "thin ultrabook laptop silver",
    ],
    "audio": [
        "over-ear premium headphones leather cushion",
        "wireless earbuds in charging case open",
        "portable Bluetooth speaker cylindrical",
    ],
    "cameras": [
        "DSLR camera with lens attached professional",
        "mirrorless camera compact body",
        "vintage film camera analog",
    ],
    "accessories": [
        "wireless charging pad circular",
        "power bank portable charger",
        "mechanical gaming keyboard RGB",
        "ergonomic wireless mouse",
    ],
}

# ─────────────────────────────────────────────
# CLIPARTS
# ─────────────────────────────────────────────

CLIPARTS = {
    "arrows": [
        "glossy 3D red arrow pointing right",
        "curved metallic blue arrow",
        "3D gold arrow pointing upward",
    ],
    "hearts": [
        "glossy 3D red heart shape",
        "metallic gold heart shape reflective",
        "heart made of real red roses",
        "glass crystal heart transparent",
    ],
    "ribbons_banners": [
        "satin golden ribbon banner unfurled",
        "red silk victory ribbon",
        "blue satin award ribbon rosette",
        "gold medal with ribbon award",
    ],
    "checkmarks_x": [
        "3D green checkmark glossy tick",
        "3D red X cross mark",
        "metallic gold star rating five point",
        "3D thumbs up hand realistic",
        "jeweled gold crown royal",
    ],
    "symbols": [
        "metallic peace sign symbol",
        "infinity symbol chrome reflective",
        "nautical anchor brass",
        "four leaf clover green realistic",
    ],
}

# ─────────────────────────────────────────────
# FURNITURE
# ─────────────────────────────────────────────

FURNITURE = {
    "seating": [
        "modern minimalist white armchair",
        "classic wooden rocking chair",
        "deep blue velvet tufted sofa",
        "executive leather office chair",
        "natural rattan peacock chair",
    ],
    "tables": [
        "tempered glass top coffee table",
        "solid wood farmhouse dining table",
        "Italian marble top side table",
    ],
    "storage": [
        "tall oak bookshelf with books",
        "modern white sliding door wardrobe",
        "vintage wooden chest of drawers",
    ],
    "beds": [
        "king size wooden platform bed frame",
        "children wooden bunk bed",
        "luxury upholstered tufted headboard bed",
    ],
}

# ─────────────────────────────────────────────
# TOOLS
# ─────────────────────────────────────────────

TOOLS = {
    "hand_tools": [
        "steel claw hammer wooden handle",
        "chrome adjustable wrench",
        "professional screwdriver set in case",
        "combination pliers red handle",
        "retractable steel measuring tape",
    ],
    "kitchen_tools": [
        "Damascus steel chef knife set in block",
        "olive wood spatula and spoon set",
        "Lodge cast iron skillet seasoned",
        "stainless steel mixing bowl set nested",
        "deep ladle stainless long handle",
    ],
    "garden_tools": [
        "steel garden spade with ash handle",
        "bypass pruning shears sharp",
        "galvanized green watering can",
        "hand trowel with ergonomic grip",
    ],
    "power_tools": [
        "cordless DeWalt electric drill",
        "Bosch angle grinder",
        "Makita circular saw",
        "random orbital sander",
    ],
}

# ─────────────────────────────────────────────
# FESTIVALS
# ─────────────────────────────────────────────

FESTIVALS = {
    "diwali": [
        "brass diya oil lamp with flame glowing",
        "colorful rangoli floor pattern with flowers",
        "golden Lakshmi idol detailed",
        "decorated Diwali gift box with ribbon",
        "lit sparkler trail of light",
    ],
    "christmas": [
        "decorated Christmas pine tree with ornaments",
        "realistic Santa Claus figurine detailed",
        "fresh Christmas wreath with holly berries",
        "wrapped Christmas gift box red ribbon gold",
    ],
    "pongal": [
        "overflowing pongal pot with rice traditional",
        "fresh sugarcane stalk long",
        "white rice flour kolam floor art",
        "sweet pongal in clay pot",
    ],
    "eid": [
        "golden crescent moon and star ornament",
        "ornate Eid lantern fanoos lit",
        "fresh dates fruit on silver plate",
    ],
    "general": [
        "birthday cake with lit candles frosted",
        "helium balloon bunch colorful shiny",
        "exploding party popper with confetti",
        "black graduation cap with tassel",
        "gold trophy cup engraved",
        "gift box wrapped with satin ribbon bow",
    ],
}

# ─────────────────────────────────────────────
# BIRDS & INSECTS
# ─────────────────────────────────────────────

BIRDS_INSECTS = {
    "birds": [
        "male peacock with full tail feathers displayed",
        "colorful macaw parrot on branch",
        "kingfisher bird vivid blue and orange",
        "pink flamingo standing one leg",
        "barn owl perched with intense eyes",
        "white dove pigeon in flight",
        "Indian mynah bird standing",
        "green parakeet perched",
    ],
    "butterflies": [
        "monarch butterfly orange and black wings open",
        "blue morpho butterfly iridescent wings",
        "swallowtail butterfly yellow and black",
    ],
    "insects": [
        "ladybug seven spots on green leaf",
        "honeybee collecting pollen on flower",
        "dragonfly iridescent wings resting",
    ],
}


# ═════════════════════════════════════════════
# CONTENT-BASED FILENAME (Skip Fix)
# ═════════════════════════════════════════════

def make_content_filename(category: str, subcategory: str, subject: str) -> str:
    """
    Stable filename from content — NOT from index.
    Same subject always same filename -> skip on re-run.
    """
    raw = f"{category}|{subcategory}|{subject}"
    h = hashlib.md5(raw.encode("utf-8")).hexdigest()[:8]
    slug_cat = re.sub(r"[^a-z0-9]", "_", category.lower())
    slug_sub = re.sub(r"[^a-z0-9]", "_", subcategory.lower())
    return f"{slug_cat}_{slug_sub}_{h}.png"


# ═════════════════════════════════════════════
# PROMPT GENERATOR CLASS V3
# ═════════════════════════════════════════════

class PromptEngine:

    def __init__(self):
        self.prompt_list = []

    def make_prompt(self, subject, extra_details=""):
        angle    = random.choice(CAMERA_ANGLES)
        lighting = random.choice(LIGHTING_STYLES)
        quality  = random.choice(DETAIL_QUALITY)
        style    = random.choice(PHOTO_STYLES)
        parts = [subject]
        if extra_details:
            parts.append(extra_details)
        parts.extend([angle, lighting, quality, style, BASE_SUFFIX])
        return ", ".join(parts)

    def _entry(self, category, subcategory, subject, prompt):
        fname = make_content_filename(category, subcategory, subject)
        return {
            "category": category, "subcategory": subcategory,
            "prompt": prompt, "seed": random.randint(1, 999999),
            "filename": fname,
        }

    # ─── ANIMALS ─────────────────────────────
    def generate_animal_prompts(self):
        prompts = []
        poses = ["standing side profile view", "facing forward looking at camera",
                 "in natural relaxed pose", "close-up portrait head detail",
                 "full body view isolated", "alert and attentive stance"]
        approaches = ["wildlife photography style", "studio animal portrait", "nature documentary quality"]
        for atype, animals in ANIMALS.items():
            for animal in animals:
                for pose in poses:
                    for approach in approaches:
                        subject = f"{animal}_{pose}_{approach}"
                        p = self.make_prompt(f"{animal}, {pose}, {approach}")
                        prompts.append(self._entry("animals", atype, subject, p))
        return prompts

    # ─── RAW MEAT & EGGS ─────────────────────
    def generate_raw_meat_prompts(self):
        prompts = []
        views = ["top-down flat lay view on white surface",
                 "45 degree angle close-up",
                 "front view on white tray",
                 "close-up macro showing texture"]
        for mtype, items in RAW_MEAT.items():
            for item in items:
                for view in views:
                    subject = f"{item}_{view}"
                    p = self.make_prompt(f"{item}, {view}, raw food ingredient photography")
                    prompts.append(self._entry("raw_meat", mtype, subject, p))
        return prompts

    # ─── INDIAN FOOD ─────────────────────────
    def generate_food_prompts(self):
        prompts = []
        photo_approaches = ["close-up food photography", "overhead flat lay food shot",
                            "angled hero shot food photography", "lifestyle food photography"]
        for dish, data in INDIAN_FOOD.items():
            for type_ in data["types"]:
                for vessel in data["vessels"]:
                    for garnish in data["garnish"][:2]:
                        for style_ in data["style"]:
                            subject = f"{type_}_{vessel}_{garnish[:20]}_{style_}"
                            p = self.make_prompt(f"{type_} served in {vessel}, {garnish}, {style_}")
                            prompts.append(self._entry("food_indian", dish, subject, p))
        vessels_world = ["on rustic wooden board", "on white ceramic dinner plate",
                         "in deep ceramic bowl", "on dark slate serving board"]
        for dish, items in WORLD_FOOD.items():
            for item in items:
                for vessel in vessels_world:
                    for approach in photo_approaches:
                        subject = f"{item}_{vessel}_{approach}"
                        p = self.make_prompt(f"{item}, {vessel}, {approach}")
                        prompts.append(self._entry("food_world", dish, subject, p))
        return prompts

    # ─── VEGETABLES ──────────────────────────
    def generate_vegetable_prompts(self):
        prompts = []
        contexts = ["whole intact fresh", "sliced cross section showing inside",
                    "arranged in group pile fresh", "with water droplets fresh harvest",
                    "close-up surface texture detail"]
        for vtype, vegs in VEGETABLES.items():
            for veg in vegs:
                for context in contexts:
                    subject = f"{veg}_{context}"
                    p = self.make_prompt(f"{veg}, {context}")
                    prompts.append(self._entry("vegetables", vtype, subject, p))
        return prompts

    # ─── FRUITS ──────────────────────────────
    def generate_fruit_prompts(self):
        prompts = []
        contexts = ["whole intact fresh", "sliced cross section showing inside",
                    "arranged in group pile", "with water droplets fresh"]
        for ftype, fruits in FRUITS.items():
            for fruit in fruits:
                for context in contexts:
                    subject = f"{fruit}_{context}"
                    p = self.make_prompt(f"{fruit}, {context}")
                    prompts.append(self._entry("fruits", ftype, subject, p))
        return prompts

    # ─── FLOWERS ─────────────────────────────
    def generate_flower_prompts(self):
        prompts = []
        approaches = ["macro lens close-up photography", "botanical studio photography",
                      "fine art floral photography"]
        for ftype, varieties in FLOWERS.items():
            for variety in varieties:
                for stage in FLOWER_STAGES:
                    for context in FLOWER_CONTEXT:
                        for approach in approaches:
                            subject = f"{variety}_{stage}_{context}"
                            p = self.make_prompt(f"{variety} {stage}, {context}, {approach}")
                            prompts.append(self._entry("flowers", ftype, subject, p))
        return prompts

    # ─── FRAMES & BORDERS ────────────────────
    def generate_frame_prompts(self):
        prompts = []
        colors = ["gold", "silver", "rose gold", "antique bronze", "pearl white"]
        styles = ["ornate hand carved detailed", "minimal clean modern",
                  "vintage aged patina", "floral intricate relief"]
        for ftype, frames in FRAMES_BORDERS.items():
            for frame in frames:
                for color in colors:
                    for style_ in styles:
                        subject = f"{frame}_{color}_{style_}"
                        p = (f"{frame}, {color} color, {style_} design, "
                             f"isolated on solid light grey background, "
                             f"photorealistic material texture, 8k high detail, "
                             f"professional product photography")
                        prompts.append(self._entry("frames_borders", ftype, subject, p))
        return prompts

    # ─── SMOKE & EFFECTS ─────────────────────
    def generate_smoke_prompts(self):
        prompts = []
        sizes = ["thin wispy", "medium thick", "dense heavy"]
        movements = ["rising upward", "swirling slowly", "dispersing outward", "curling sideways"]
        smoke_suffix = ("isolated on solid light grey background, high contrast, "
                        "sharp edges, 8k resolution, real smoke photography")
        for etype, effects in SMOKE_EFFECTS.items():
            for effect in effects:
                for size in sizes:
                    for movement in movements:
                        subject = f"{effect}_{size}_{movement}"
                        p = f"{size} {effect}, {movement}, {smoke_suffix}"
                        prompts.append(self._entry("effects", etype, subject, p))
        return prompts

    # ─── SKY & CELESTIAL ─────────────────────
    def generate_sky_prompts(self):
        prompts = []
        styles = ["photorealistic rendering", "high detail realistic", "3D metallic finish"]
        moods = ["warm golden tones", "cool blue tones", "vivid bright colors"]
        for etype, elements in SKY_ELEMENTS.items():
            for element in elements:
                for style_ in styles:
                    for mood in moods:
                        subject = f"{element}_{style_}_{mood}"
                        p = self.make_prompt(f"{element}, {style_}, {mood}")
                        prompts.append(self._entry("sky_celestial", etype, subject, p))
        return prompts

    # ─── OFFER LOGOS ─────────────────────────
    def generate_offer_logo_prompts(self):
        prompts = []
        colors = ["red and gold", "blue and white", "green and yellow", "orange and white"]
        badges = ["starburst explosion shape", "circular seal stamp",
                  "ribbon banner label", "shield badge shape"]
        for otype, offers in OFFER_LOGOS.items():
            for offer in offers:
                for color in colors:
                    for badge in badges:
                        subject = f"{offer}_{color}_{badge}"
                        p = f"{offer} as {badge}, {color} color scheme, {VECTOR_SUFFIX}"
                        prompts.append(self._entry("offer_logos", otype, subject, p))
        return prompts

    # ─── VEHICLES ────────────────────────────
    def generate_vehicle_prompts(self):
        prompts = []
        car_details = ["pristine clean polished bodywork", "gleaming factory fresh paintwork"]
        for ctype, models in CARS.items():
            for model in models:
                for angle in CAR_ANGLES:
                    for detail in car_details:
                        subject = f"{model}_{angle}_{detail}"
                        p = self.make_prompt(f"{model}, {angle}", detail)
                        prompts.append(self._entry("vehicles_cars", ctype, subject, p))
        bike_details = ["chrome exhaust gleaming", "shiny tank and bodywork"]
        for btype, models in BIKES.items():
            for model in models:
                for angle in CAR_ANGLES:
                    for detail in bike_details:
                        subject = f"{model}_{angle}_{detail}"
                        p = self.make_prompt(f"{model}, {angle}", detail)
                        prompts.append(self._entry("vehicles_bikes", btype, subject, p))
        return prompts

    # ─── TREES & NATURE ──────────────────────
    def generate_nature_prompts(self):
        prompts = []
        seasons = ["summer lush green foliage", "spring fresh blossoms", "monsoon rain glistening wet"]
        for ttype, trees in TREES.items():
            for tree in trees:
                for context in TREE_CONTEXT:
                    for season in seasons:
                        subject = f"{tree}_{context}_{season}"
                        p = self.make_prompt(f"{tree}, {context}, {season}")
                        prompts.append(self._entry("nature_trees", ttype, subject, p))
        return prompts

    # ─── POTS & VESSELS ──────────────────────
    def generate_pots_prompts(self):
        prompts = []
        finishes = ["brand new clean", "aged patina surface", "polished shiny reflective", "hand painted floral motif"]
        sizes = ["small", "medium", "large"]
        for ptype, pots in POTS_VESSELS.items():
            for pot in pots:
                for finish in finishes:
                    for size in sizes:
                        subject = f"{pot}_{finish}_{size}"
                        p = self.make_prompt(f"{size} {pot}, {finish}")
                        prompts.append(self._entry("pots_vessels", ptype, subject, p))
        return prompts

    # ─── FESTIVALS ───────────────────────────
    def generate_festival_prompts(self):
        prompts = []
        styles = ["studio product photography", "close-up detail photography"]
        moods = ["festive warm glow", "traditional authentic feel", "vibrant colorful bright"]
        for ftype, items in FESTIVALS.items():
            for item in items:
                for style_ in styles:
                    for mood in moods:
                        subject = f"{item}_{style_}_{mood}"
                        p = self.make_prompt(f"{item}, {style_}, {mood}")
                        prompts.append(self._entry("festivals", ftype, subject, p))
        return prompts

    # ─── BIRDS & INSECTS ─────────────────────
    def generate_bird_insect_prompts(self):
        prompts = []
        contexts = ["perched on natural branch", "in alert natural pose",
                    "detailed portrait close-up", "full body side view"]
        for ctype, creatures in BIRDS_INSECTS.items():
            for creature in creatures:
                for context in contexts:
                    subject = f"{creature}_{context}"
                    p = self.make_prompt(f"{creature}, {context}, wildlife photography")
                    prompts.append(self._entry("birds_insects", ctype, subject, p))
        return prompts

    # ─── JEWELLERY ───────────────────────────
    def generate_jewellery_prompts(self):
        prompts = []
        finishes = ["mirror polished gold", "diamonds sparkling faceted", "antique oxidized finish"]
        contexts = ["on white marble surface", "floating isolated clean", "on black velvet display cushion"]
        for jtype, jewels in JEWELLERY.items():
            for jewel in jewels:
                for finish in finishes:
                    for context in contexts:
                        subject = f"{jewel}_{finish}_{context}"
                        p = self.make_prompt(f"{jewel}, {finish}, {context}")
                        prompts.append(self._entry("jewellery", jtype, subject, p))
        return prompts

    # ─── SPICES ──────────────────────────────
    def generate_spice_prompts(self):
        prompts = []
        for stype, spices in SPICES.items():
            for spice in spices:
                for context in SPICE_CONTEXT:
                    subject = f"{spice}_{context}"
                    p = self.make_prompt(f"{spice}, {context}, aromatic food photography")
                    prompts.append(self._entry("spices", stype, subject, p))
        return prompts

    # ─── BEVERAGES ───────────────────────────
    def generate_beverage_prompts(self):
        prompts = []
        moods = ["warm cozy atmosphere", "refreshing cool tone", "elegant fine dining style"]
        for btype, beverages in BEVERAGES.items():
            for beverage in beverages:
                for mood in moods:
                    subject = f"{beverage}_{mood}"
                    p = self.make_prompt(f"{beverage}, {mood}, beverage photography")
                    prompts.append(self._entry("beverages", btype, subject, p))
        return prompts

    # ─── SHOES ───────────────────────────────
    def generate_shoe_prompts(self):
        prompts = []
        views = ["side profile single shoe", "pair from front angled", "45 degree hero shot pair"]
        for stype, shoes in SHOES.items():
            for shoe in shoes:
                for view in views:
                    subject = f"{shoe}_{view}"
                    p = self.make_prompt(f"{shoe}, {view}, footwear product photography")
                    prompts.append(self._entry("shoes", stype, subject, p))
        return prompts

    # ─── BAGS ────────────────────────────────
    def generate_bag_prompts(self):
        prompts = []
        views = ["front view standing upright", "45 degree angle showing depth", "flat lay top down"]
        for btype, bags in BAGS.items():
            for bag in bags:
                for view in views:
                    subject = f"{bag}_{view}"
                    p = self.make_prompt(f"{bag}, {view}, luxury product photography")
                    prompts.append(self._entry("bags", btype, subject, p))
        return prompts

    # ─── COSMETICS ───────────────────────────
    def generate_cosmetics_prompts(self):
        prompts = []
        views = ["front product shot clean", "45 degree beauty shot", "macro detail showing texture"]
        for ctype, items in COSMETICS.items():
            for item in items:
                for view in views:
                    subject = f"{item}_{view}"
                    p = self.make_prompt(f"{item}, {view}, beauty product photography")
                    prompts.append(self._entry("cosmetics", ctype, subject, p))
        return prompts

    # ─── SPORTS ──────────────────────────────
    def generate_sports_prompts(self):
        prompts = []
        views = ["front view on surface", "dramatic hero shot angle", "close-up detail texture"]
        for stype, items in SPORTS.items():
            for item in items:
                for view in views:
                    subject = f"{item}_{view}"
                    p = self.make_prompt(f"{item}, {view}, sports product photography")
                    prompts.append(self._entry("sports", stype, subject, p))
        return prompts

    # ─── MUSICAL INSTRUMENTS ─────────────────
    def generate_music_prompts(self):
        prompts = []
        views = ["full instrument front view", "45 degree angle showing detail", "dramatic side profile"]
        for itype, instruments in MUSICAL_INSTRUMENTS.items():
            for instrument in instruments:
                for view in views:
                    subject = f"{instrument}_{view}"
                    p = self.make_prompt(f"{instrument}, {view}, musical instrument photography")
                    prompts.append(self._entry("music", itype, subject, p))
        return prompts

    # ─── POOJA ITEMS ─────────────────────────
    def generate_pooja_prompts(self):
        prompts = []
        finishes = ["polished gleaming finish", "antique aged patina", "brand new temple quality"]
        for ptype, items in POOJA_ITEMS.items():
            for item in items:
                for finish in finishes:
                    subject = f"{item}_{finish}"
                    p = self.make_prompt(f"{item}, {finish}, devotional product photography")
                    prompts.append(self._entry("pooja_items", ptype, subject, p))
        return prompts

    # ─── CLOTHING ────────────────────────────
    def generate_clothing_prompts(self):
        prompts = []
        views = ["neatly folded on surface", "draped showing fabric flow", "flat lay full garment view"]
        for ctype, items in CLOTHING.items():
            for item in items:
                for view in views:
                    subject = f"{item}_{view}"
                    p = self.make_prompt(f"{item}, {view}, fashion product photography")
                    prompts.append(self._entry("clothing", ctype, subject, p))
        return prompts

    # ─── MEDICAL ─────────────────────────────
    def generate_medical_prompts(self):
        prompts = []
        views = ["front product shot clean", "45 degree angle detail", "flat lay arrangement"]
        for mtype, items in MEDICAL.items():
            for item in items:
                for view in views:
                    subject = f"{item}_{view}"
                    p = self.make_prompt(f"{item}, {view}, medical product photography")
                    prompts.append(self._entry("medical", mtype, subject, p))
        return prompts

    # ─── STATIONERY ──────────────────────────
    def generate_stationery_prompts(self):
        prompts = []
        views = ["front view on desk surface", "45 degree angle artistic", "flat lay arranged composition"]
        for stype, items in STATIONERY.items():
            for item in items:
                for view in views:
                    subject = f"{item}_{view}"
                    p = self.make_prompt(f"{item}, {view}, stationery product photography")
                    prompts.append(self._entry("stationery", stype, subject, p))
        return prompts

    # ─── ELECTRONICS ─────────────────────────
    def generate_electronics_prompts(self):
        prompts = []
        angles = ["front view showing screen", "45 degree angle hero shot", "side profile thin view"]
        for etype, items in ELECTRONICS.items():
            for item in items:
                for angle in angles:
                    subject = f"{item}_{angle}"
                    p = self.make_prompt(f"{item}, {angle}, tech product photography")
                    prompts.append(self._entry("electronics", etype, subject, p))
        return prompts

    # ─── CLIPARTS ────────────────────────────
    def generate_clipart_prompts(self):
        prompts = []
        styles = ["glossy 3D rendered", "polished metallic chrome", "smooth photorealistic surface"]
        colors = ["red", "blue", "gold"]
        for ctype, clips in CLIPARTS.items():
            for clip in clips:
                for style_ in styles:
                    for color in colors:
                        subject = f"{clip}_{style_}_{color}"
                        p = self.make_prompt(f"{clip}, {color} tinted, {style_}")
                        prompts.append(self._entry("cliparts", ctype, subject, p))
        return prompts

    # ─── FURNITURE ───────────────────────────
    def generate_furniture_prompts(self):
        prompts = []
        materials = ["solid oak wood grain visible", "dark mahogany polished",
                     "white painted clean", "brushed stainless steel"]
        conditions = ["brand new showroom condition", "modern minimalist design", "vintage antique style"]
        for ftype, items in FURNITURE.items():
            for item in items:
                for material in materials:
                    for condition in conditions:
                        subject = f"{item}_{material}_{condition}"
                        p = self.make_prompt(f"{item}, {material}, {condition}")
                        prompts.append(self._entry("furniture", ftype, subject, p))
        return prompts

    # ─── TOOLS ───────────────────────────────
    def generate_tools_prompts(self):
        prompts = []
        conditions = ["brand new unused", "professional grade heavy duty", "chrome plated gleaming"]
        views = ["front view flat lay", "45 degree angle view", "close-up detail macro"]
        for ttype, tools in TOOLS.items():
            for tool in tools:
                for condition in conditions:
                    for view in views:
                        subject = f"{tool}_{condition}_{view}"
                        p = self.make_prompt(f"{tool}, {condition}, {view}")
                        prompts.append(self._entry("tools", ttype, subject, p))
        return prompts

    # ═══════════════════════════════════════════
    # GENERATE ALL — PRIORITY ORDER
    # ═══════════════════════════════════════════

    def generate_all_prompts(self):
        """
        PRIORITY ORDER — NO random shuffle:
        1. Animals (farm/fish/eggs first)
        2. Raw meat & eggs
        3. Indian food
        4. Vegetables
        5. Fruits
        6. Flowers
        7+ everything else

        Content-based filenames — same image NEVER regenerated.
        """
        print("Generating prompts V3 (Priority Order)...")
        all_prompts = []

        generators = [
            # PRIORITY 1 — Indian Animals & Seafood
            ("Animals",             self.generate_animal_prompts),
            ("Raw Meat & Eggs",     self.generate_raw_meat_prompts),
            # PRIORITY 2 — Indian Food
            ("Indian Food",         self.generate_food_prompts),
            # PRIORITY 3 — Vegetables
            ("Vegetables",          self.generate_vegetable_prompts),
            # PRIORITY 4 — Fruits
            ("Fruits",              self.generate_fruit_prompts),
            # PRIORITY 5 — Flowers
            ("Flowers",             self.generate_flower_prompts),
            # PRIORITY 6 — Borders & Effects
            ("Frames/Borders",      self.generate_frame_prompts),
            ("Smoke/Effects",       self.generate_smoke_prompts),
            ("Sky/Celestial",       self.generate_sky_prompts),
            ("Cliparts 3D",         self.generate_clipart_prompts),
            ("Offer Logos",         self.generate_offer_logo_prompts),
            # PRIORITY 7 — Indian Culture
            ("Pooja Items",         self.generate_pooja_prompts),
            ("Festivals",           self.generate_festival_prompts),
            ("Jewellery",           self.generate_jewellery_prompts),
            ("Birds/Insects",       self.generate_bird_insect_prompts),
            ("Spices",              self.generate_spice_prompts),
            ("Beverages",           self.generate_beverage_prompts),
            # PRIORITY 8 — Products
            ("Clothing",            self.generate_clothing_prompts),
            ("Shoes",               self.generate_shoe_prompts),
            ("Bags",                self.generate_bag_prompts),
            ("Cosmetics",           self.generate_cosmetics_prompts),
            ("Vehicles",            self.generate_vehicle_prompts),
            ("Electronics",         self.generate_electronics_prompts),
            ("Sports",              self.generate_sports_prompts),
            ("Musical Instruments", self.generate_music_prompts),
            ("Furniture",           self.generate_furniture_prompts),
            ("Tools",               self.generate_tools_prompts),
            ("Nature/Trees",        self.generate_nature_prompts),
            ("Pots/Vessels",        self.generate_pots_prompts),
            ("Medical",             self.generate_medical_prompts),
            ("Stationery",          self.generate_stationery_prompts),
        ]

        for name, gen_func in generators:
            prev = len(all_prompts)
            all_prompts.extend(gen_func())
            print(f"  OK {name}: {len(all_prompts) - prev}")

        # Deduplicate filenames (add suffix if collision)
        from collections import Counter
        fname_count = Counter()
        for p in all_prompts:
            fname_count[p["filename"]] += 1
        fname_seen = {}
        for p in all_prompts:
            fn = p["filename"]
            if fname_count[fn] > 1:
                seen = fname_seen.get(fn, 0)
                fname_seen[fn] = seen + 1
                base = fn.rsplit(".", 1)[0]
                p["filename"] = f"{base}_{seen:03d}.png"

        # Add global index for batch slicing (skip logic uses filename NOT index)
        for i, p in enumerate(all_prompts):
            p["index"] = i
            p.setdefault("status", "pending")

        print(f"\nTOTAL PROMPTS: {len(all_prompts)}")
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
            print(f"  {cat}.json -> {len(items)} prompts")
        index = {"total": len(prompts), "categories": list(by_cat.keys()),
                 "files": [f"{c}.json" for c in by_cat]}
        with open(out / "index.json", "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2, ensure_ascii=False)
        print(f"\nSaved {len(prompts)} prompts in {output_dir}/")
        return output_dir


def load_all_prompts(splits_dir="prompts/splits"):
    splits = Path(splits_dir)
    index_file = splits / "index.json"
    if index_file.exists():
        index = json.loads(index_file.read_text())
        files = [splits / f for f in index["files"]]
    else:
        files = [f for f in sorted(splits.glob("*.json")) if f.name != "index.json"]
    all_prompts = []
    for fpath in files:
        with open(fpath, encoding="utf-8") as f:
            all_prompts.extend(json.load(f))
    print(f"Loaded {len(all_prompts)} prompts from {len(files)} files.")
    return all_prompts


if __name__ == "__main__":
    engine = PromptEngine()
    engine.save_prompts("prompts/splits")
