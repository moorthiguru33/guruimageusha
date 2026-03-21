"""
🎨 PNG Library — Prompt Engine V3 (GURU IMAGE USHA)
══════════════════════════════════════════════════════════
Categories  : 13 focused categories — Poultry/Animals, Raw Meat, Vehicles,
              Flowers, Fruits, Vegetables, Cool Drinks, Indian Foods,
              World Foods, Footwear, Indian Dress, Jewellery Models,
              Office Models
Per Item    : 30+ unique prompts guaranteed (combinatorial expansion)
Style       : 100% Photorealistic — NO cartoon / illustration / watercolor
Background  : Solid Light Grey (#D3D3D3) — all images
══════════════════════════════════════════════════════════
"""

import random
import json
from pathlib import Path

# ─────────────────────────────────────────────────────────────
# BASE SUFFIXES
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
# UNIVERSAL VARIATION BANKS
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
    "dramatic Rembrandt side lighting",
    "bright even fill lighting",
    "warm key light with cool fill",
    "high key bright studio lighting",
    "rim light with soft fill",
]

DETAIL_QUALITY = [
    "intricate surface texture visible",
    "ultra fine material detail",
    "every pore and grain visible",
    "lifelike realistic texture",
    "tactile surface quality",
    "true-to-life rendering",
]

PHOTO_STYLES = [
    "commercial product photography",
    "editorial magazine photography",
    "studio catalog photography",
    "high-end advertising photography",
]

# ─────────────────────────────────────────────────────────────
# 1. LIVE POULTRY & ANIMALS
# ─────────────────────────────────────────────────────────────

ROOSTER = {
    "breeds": [
        "Indian country rooster with bright red comb",
        "black Australorp rooster with green sheen feathers",
        "golden Buff Orpington rooster fluffy",
        "red Rhode Island Red rooster robust",
        "white Leghorn rooster tall and proud",
        "colorful jungle fowl rooster wild type",
        "grey Brahma rooster large feathered feet",
        "Kadaknath black rooster jet black feathers",
        "multi-colored bantam rooster small ornamental",
        "Aseel fighting rooster muscular compact",
    ],
    "poses": [
        "standing alert with chest puffed up",
        "side profile full body view",
        "crowing beak open pose",
        "pecking downward pose",
        "head turned showing profile",
        "perched on branch raised position",
    ],
    "details": [
        "bright red fleshy comb and wattles clearly visible",
        "vivid tail feathers fanned out dramatically",
        "sharp curved talons on feet visible",
        "glossy iridescent wing feathers detail",
        "detailed eye and beak close-up",
    ],
}

BROILER_CHICKEN = {
    "types": [
        "plump white broiler chicken whole",
        "heavy broiler hen large breast",
        "medium sized broiler chicken standing",
        "white Cornish cross broiler chicken",
        "young broiler chicken growing stage",
        "fully grown commercial broiler chicken",
        "free range broiler chicken healthy",
        "organic raised broiler chicken",
    ],
    "poses": [
        "standing full body side view",
        "front view facing camera",
        "foraging pecking ground pose",
        "resting calm relaxed position",
        "alert head raised standing",
        "close-up portrait head detail",
    ],
    "details": [
        "clean white feathers detailed texture",
        "healthy pink comb and wattles",
        "thick muscular breast visible",
        "detailed foot and toe structure",
        "full body profile showing size",
    ],
}

GOAT = {
    "types": [
        "white Beetal goat with long ears",
        "black and white Sirohi goat",
        "brown Jamnapari goat tall",
        "small Barbari goat spotted",
        "Malabari goat dark brown",
        "Osmanabadi black goat sturdy",
        "Boer goat white with red head",
        "Nubians goat long floppy ears",
        "Billy goat male with beard and horns",
        "Nanny goat female",
    ],
    "poses": [
        "standing alert side profile view",
        "facing camera front view",
        "grazing head down pose",
        "resting sitting calm",
        "alert head raised ears forward",
        "full body 3/4 angle view",
    ],
    "details": [
        "curved horns clearly visible",
        "soft fur coat texture detail",
        "beard and facial features detail",
        "hooves and leg structure visible",
        "eye and ear detail close-up",
    ],
}

QUAIL = {
    "types": [
        "Japanese quail brown speckled pattern",
        "Coturnix quail male with chest marking",
        "white quail domestic breed",
        "Indian grey quail wild type",
        "bobwhite quail brown striped",
        "button quail tiny smallest breed",
    ],
    "poses": [
        "standing plump side profile",
        "front view facing camera",
        "foraging ground pecking pose",
        "alert head raised erect",
        "resting calm full body",
        "close-up portrait head detail",
    ],
    "details": [
        "speckled feather pattern texture detail",
        "small rounded plump body shape",
        "tiny beak and eye detail",
        "short tail and wing detail",
        "leg and toe structure visible",
    ],
}

COW = {
    "types": [
        "white Gir cow with hump sacred Indian breed",
        "black and white Holstein dairy cow",
        "brown Tharparkar cow desert breed",
        "Sahiwal reddish brown dairy cow",
        "white Kankrej cow large prominent hump",
        "Ongole white cow massive build",
        "Kangayam grey cow South Indian breed",
        "Hallikar brown cow Karnataka breed",
        "Brahman cow grey with large hump",
        "desi country cow traditional Indian",
    ],
    "poses": [
        "standing full body side profile",
        "facing camera front view",
        "grazing head down position",
        "resting lying calm peaceful",
        "alert head raised facing front",
        "walking gentle motion captured",
    ],
    "details": [
        "prominent hump on back clearly visible",
        "long curved horns detailed",
        "soft brown eyes detail close-up",
        "dewlap loose skin under neck visible",
        "udder detail full body view",
    ],
}

# ─────────────────────────────────────────────────────────────
# 2. RAW MEAT & EGGS
# ─────────────────────────────────────────────────────────────

RAW_CHICKEN_MEAT = {
    "cuts": [
        "whole raw chicken cleaned dressed",
        "raw chicken breast fillets boneless",
        "raw chicken thighs with bone-in",
        "raw chicken drumsticks cluster",
        "raw chicken wings flat arranged",
        "raw chicken leg quarter pieces",
        "raw whole chicken cut into curry pieces",
        "raw chicken liver dark red",
        "raw chicken gizzard pieces cleaned",
        "raw chicken neck and back pieces",
    ],
    "presentation": [
        "arranged on white ceramic plate",
        "on fresh green banana leaf",
        "on dark slate board clean",
        "on stainless steel tray",
        "in white plastic food tray",
        "arranged neatly close-up macro",
    ],
    "details": [
        "fresh pink raw meat texture",
        "glistening moist surface detail",
        "clean cut cross section visible",
        "fresh not frozen appearance",
        "butcher quality presentation",
    ],
}

RAW_GOAT_MEAT = {
    "cuts": [
        "raw goat mutton curry cut pieces",
        "raw goat leg whole bone-in",
        "raw goat chops rack with ribs",
        "raw goat shoulder piece bone-in",
        "raw goat liver dark maroon",
        "raw goat kidney pair cleaned",
        "raw goat ribs individual pieces",
        "raw goat minced keema pile",
        "raw goat neck bone pieces",
        "raw goat brain cleaned halved",
    ],
    "presentation": [
        "on fresh green banana leaf",
        "on white ceramic plate arranged",
        "on dark wooden chopping board",
        "on steel tray market style",
        "close-up macro meat texture",
        "stacked pile presentation",
    ],
    "details": [
        "deep red raw mutton color",
        "visible marbling fat texture",
        "fresh cut surface glistening",
        "bone marrow visible in cuts",
        "butcher shop quality fresh",
    ],
}

RAW_QUAIL_MEAT = {
    "cuts": [
        "whole raw quail cleaned dressed single",
        "pair of raw quail birds cleaned",
        "three whole raw quail arranged",
        "raw quail split halved open",
        "raw quail with head intact",
        "raw quail without head cleaned",
        "raw quail on banana leaf",
        "raw quail small plump body",
    ],
    "presentation": [
        "on fresh green banana leaf",
        "on white ceramic plate",
        "on dark slate board",
        "in steel tray arranged",
        "close-up texture detail",
        "neat row arrangement",
    ],
    "details": [
        "small delicate body texture",
        "pale yellowish skin surface",
        "clean dressed ready to cook",
        "tiny wings folded neatly",
        "fresh glistening appearance",
    ],
}

EGGS = {
    "types": [
        "single white chicken egg perfect",
        "single brown chicken egg natural",
        "cluster of brown farm eggs",
        "white eggs in wicker basket",
        "brown eggs pile rustic",
        "quail eggs small speckled cluster",
        "quail eggs speckled pattern macro",
        "duck eggs large pale",
        "Indian desi country chicken eggs brown",
        "fertile eggs arranged in row",
        "cracked egg showing yolk runny",
        "half dozen eggs in carton",
    ],
    "presentation": [
        "on wooden surface natural",
        "in wicker straw basket",
        "on white ceramic plate",
        "on grey stone surface",
        "scattered on linen cloth",
        "stacked neat arrangement",
    ],
    "details": [
        "natural matte eggshell texture",
        "subtle speckle pattern detail",
        "smooth oval perfect form",
        "yolk visible through crack",
        "fresh farm quality appearance",
    ],
}

MEAT_STYLE = [
    "butcher shop product photography",
    "food market product photography",
    "fresh meat studio photography",
    "commercial food photography",
]

# ─────────────────────────────────────────────────────────────
# 3. VEHICLES — INDIAN FOCUS
# ─────────────────────────────────────────────────────────────

INDIAN_CARS = {
    "hatchback": [
        "Maruti Suzuki Alto used white 2018 model",
        "Hyundai i20 red used 2019 model",
        "Maruti Suzuki Swift blue 2020 model used",
        "Tata Tiago silver used 2018 model",
        "Renault Kwid used orange 2019 model",
        "Honda Brio used red 2017 model",
        "Maruti Wagon R white used 2019 model",
        "Tata Punch used red 2021 model",
    ],
    "sedan": [
        "Honda City silver used 2019 model",
        "Maruti Dzire white used 2020 model",
        "Toyota Etios used silver 2018 model",
        "Hyundai Verna blue used 2019 model",
        "Honda Amaze used silver 2020 model",
        "Tata Tigor used white 2018 model",
    ],
    "suv": [
        "Mahindra Scorpio black used 2019 model",
        "Hyundai Creta grey used 2020 model",
        "Kia Seltos used white 2021 model",
        "Tata Nexon red used 2020 model",
        "Maruti Brezza used silver 2019 model",
        "Mahindra Bolero white used 2018 model",
        "Ford EcoSport blue used 2019 model",
    ],
    "mpv": [
        "Maruti Suzuki Omni white used van",
        "Tata Ace small tempo truck used",
        "Mahindra Xylo used white MPV",
        "Toyota Innova silver used MPV 2019",
        "Chevrolet Enjoy used white MPV",
    ],
}

INDIAN_BIKES = {
    "commuter": [
        "Hero Splendor Plus black 2019 used",
        "Bajaj Pulsar 150 blue used 2019",
        "Honda CB Shine used silver 2018",
        "TVS Apache RTR 160 red used",
        "Hero HF Deluxe black used commuter",
        "Bajaj CT100 used black commuter",
        "Honda Unicorn silver used 2018",
        "TVS Star City used black 2019",
    ],
    "sports": [
        "Bajaj Pulsar NS200 black sports used",
        "TVS Apache RR310 used black sports",
        "Yamaha R15 V3 red sports used",
        "KTM Duke 200 orange used sports",
        "Royal Enfield Thunderbird 350 used black",
        "Bajaj Dominar 400 used black",
    ],
    "classic": [
        "Royal Enfield Classic 350 black used",
        "Royal Enfield Bullet 350 used black",
        "Royal Enfield Meteor 350 used blue",
        "Jawa 42 used maroon classic",
        "Royal Enfield Himalayan grey used",
    ],
    "scooter": [
        "Honda Activa 6G used silver scooter",
        "TVS Jupiter used grey scooter",
        "Suzuki Access 125 used grey",
        "Yamaha Fascino used blue scooter",
        "Hero Maestro Edge used red scooter",
        "TVS Ntorq 125 used sports scooter",
    ],
}

AUTO_RICKSHAW = {
    "types": [
        "yellow black Indian auto rickshaw three-wheeler",
        "green yellow auto rickshaw passenger",
        "Bajaj RE auto rickshaw yellow classic",
        "TVS King auto rickshaw yellow",
        "electric auto rickshaw green modern",
        "decorated auto rickshaw colorful Indian",
        "auto rickshaw front view showing meter",
        "auto rickshaw side profile classic",
        "cargo auto rickshaw load carrier",
        "school auto rickshaw yellow",
    ],
    "angles": [
        "front 3/4 view showing handlebars and seating",
        "side profile full view",
        "rear 3/4 view showing passenger area",
        "front view symmetrical straight on",
        "low angle dramatic hero shot",
        "top aerial view showing roof",
    ],
    "details": [
        "shiny painted metal bodywork",
        "rubber tires and wheel detail",
        "meter and steering detail",
        "passenger seating interior visible",
        "engine cover side detail",
    ],
}

CAR_ANGLES_V = [
    "front 3/4 view showing grille and headlights",
    "side profile full length view",
    "rear 3/4 view showing tail lights",
    "dramatic front view symmetrical",
    "top aerial bird eye view",
    "dynamic low angle hero shot",
]

CAR_DETAILS = [
    "pristine clean polished bodywork",
    "detailed wheel rim close-up",
    "gleaming paintwork with subtle reflections",
    "clean exterior showroom quality",
    "side profile full length clean",
]

# ─────────────────────────────────────────────────────────────
# 4. FLOWERS — SINGLE & BATCH
# ─────────────────────────────────────────────────────────────

FLOWERS_SINGLE = {
    "rose": [
        "deep red velvet single rose",
        "soft pink garden rose",
        "pure white rose",
        "bright yellow rose",
        "sunset orange rose",
        "royal purple rose",
        "peach blush rose",
        "dark burgundy rose",
        "coral pink rose",
        "bicolor red and white rose",
    ],
    "lotus": [
        "pink lotus flower in full bloom",
        "pure white lotus open petals",
        "purple lotus with golden center",
        "red lotus bud beginning to open",
        "lotus flower with green lily pad",
        "pale pink lotus side view",
    ],
    "jasmine": [
        "white jasmine flower cluster fresh",
        "arabian jasmine buds tight",
        "star jasmine fully open petals",
        "jasmine garland fresh string",
        "jasmine single bloom white",
        "jasmine with green leaf",
    ],
    "marigold": [
        "deep orange marigold full bloom",
        "bright yellow marigold round",
        "large African marigold pompom",
        "marigold bunch tied together",
        "marigold side profile view",
        "marigold petals detail macro",
    ],
    "sunflower": [
        "large yellow sunflower head full bloom",
        "sunflower with seeds center visible",
        "sunflower fully open face front",
        "sunflower with green stem leaves",
        "small dwarf sunflower compact",
        "sunflower bud just opening",
    ],
    "lily": [
        "elegant white calla lily single",
        "spotted orange tiger lily",
        "fragrant pink stargazer lily",
        "yellow Asiatic lily full bloom",
        "purple water lily floating",
        "white Easter lily trumpet shaped",
    ],
    "hibiscus": [
        "bright red hibiscus with yellow stamen",
        "yellow hibiscus tropical bloom",
        "pink double hibiscus ruffled",
        "white hibiscus delicate single",
        "coral hibiscus large open bloom",
        "dark red hibiscus side view",
    ],
    "orchid": [
        "purple phalaenopsis orchid spray",
        "white dendrobium orchid stem",
        "pink cymbidium orchid bloom",
        "yellow oncidium orchid cluster",
        "spotted exotic orchid pattern",
        "red cattleya orchid large",
    ],
    "other_flowers": [
        "cherry blossom branch pink blooms",
        "lavender stems bunch purple",
        "dahlia flower multi-layered petals",
        "lush peony bloom soft pink",
        "red tulip flower single",
        "purple iris flower",
        "gerbera daisy bright orange",
        "red anthurium heart shaped",
    ],
}

FLOWERS_BATCH = [
    "assorted mixed flower bouquet colorful arrangement",
    "roses and jasmine mixed bouquet",
    "marigold and rose batch arrangement",
    "lotus and lily mixed arrangement",
    "tropical flower variety spread flat lay",
    "Indian pooja flower arrangement mixed",
    "flower market variety bundle colorful",
    "seasonal mixed flowers flat lay arrangement",
    "dozen roses bouquet red mixed",
    "wedding flower arrangement mixed white and pink",
    "carnation and rose mixed batch",
    "sunflower and marigold batch together",
    "jasmine garland and loose flowers batch",
    "bridal flower arrangement batch white flowers",
    "colorful spring flower variety bunch",
    "flower basket overflowing mixed varieties",
    "Indian temple flower batch marigold jasmine",
    "red and white rose batch arrangement",
    "tropical hibiscus and orchid batch",
    "dahlia peony rose luxury batch bouquet",
    "country wildflower batch natural mix",
    "flower vendor bundle market style",
    "festival flower batch bright colors",
    "aromatic flower batch jasmine rose mix",
    "lilies and irises batch modern arrangement",
    "chrysanthemum batch full bloom variety",
    "gerbera daisy colorful batch mix",
    "fresh harvest flower batch green leaves",
    "mixed flower spread top-down flat lay",
    "all flowers variety collection batch display",
]

FLOWER_STAGES = ["in full bloom", "half open bud", "just opening fresh", "tight bud"]
FLOWER_CONTEXTS = [
    "single long stem",
    "with morning dewdrops on petals",
    "with fresh green leaves attached",
    "freshly cut close-up",
    "in small glass vase",
    "on light grey surface",
]
FLOWER_PHOTO = [
    "macro lens close-up floral photography",
    "botanical studio photography",
    "fine art floral photography",
    "natural light floral photography",
]

# ─────────────────────────────────────────────────────────────
# 5. FRUITS — SINGLE & BATCH
# ─────────────────────────────────────────────────────────────

FRUITS_SINGLE = {
    "mango": [
        "ripe Alphonso mango golden yellow",
        "green raw mango unripe",
        "Kesar mango orange ripe",
        "Banganapalli mango large ripe",
        "ripe mango sliced cross section",
        "mango halved showing seed",
        "small green totapuri mango",
        "bunch of small local mangoes",
        "Ratnagiri mango premium quality",
        "mango with leaf attached fresh",
    ],
    "banana": [
        "single ripe yellow banana",
        "bunch of yellow bananas",
        "small Yelakki banana cluster",
        "red banana variety ripe",
        "peeled banana showing white flesh",
        "green raw banana single",
        "plantain cooking banana raw green",
        "very ripe banana dark yellow spots",
    ],
    "apple": [
        "shiny red Shimla apple single",
        "green Granny Smith apple",
        "pink Lady apple blush color",
        "red apple halved showing seeds",
        "apple slice fan arrangement",
        "yellow golden apple variety",
        "apple with stem and leaf",
        "small crabapple deep red",
    ],
    "watermelon": [
        "whole watermelon large round",
        "watermelon slice triangular red flesh",
        "watermelon half cut showing red inside",
        "watermelon cubes arranged",
        "mini watermelon small whole",
        "watermelon with seeds black visible",
    ],
    "grapes": [
        "purple grapes bunch on vine",
        "green seedless grapes cluster",
        "red globe grapes bunch",
        "black grapes dark glossy cluster",
        "single grape close-up macro",
        "grapes with vine and leaves",
    ],
    "papaya": [
        "ripe yellow papaya whole",
        "papaya halved showing orange flesh and seeds",
        "raw green papaya whole",
        "papaya slice arranged pieces",
        "small round papaya variety",
        "papaya with seeds visible",
    ],
    "coconut": [
        "green tender coconut whole fresh",
        "coconut with straw ready to drink",
        "half split coconut white flesh",
        "mature brown coconut whole",
        "coconut halved dry inside",
        "cluster of three coconuts together",
    ],
    "pomegranate": [
        "whole red pomegranate round",
        "pomegranate halved showing red seeds",
        "pomegranate arils seeds scattered",
        "pomegranate crown detail macro",
        "deep red pomegranate variety",
        "pomegranate quarter wedge cut",
    ],
    "pineapple": [
        "whole pineapple with crown fresh",
        "pineapple slice ring cross section",
        "pineapple halved showing yellow flesh",
        "pineapple spear wedge cut",
        "baby pineapple small whole",
        "pineapple chunks pieces cubed",
    ],
    "guava": [
        "white guava round whole ripe",
        "pink flesh guava halved",
        "green guava unripe whole",
        "guava slice showing seeds",
        "small bunch guava cluster",
        "guava with leaf attached fresh",
    ],
    "orange": [
        "bright orange ripe orange single",
        "orange halved showing juicy segments",
        "blood orange deep red inside",
        "orange peeled segments spread",
        "navel orange whole with navel",
        "orange slice round cross section",
    ],
    "lemon_lime": [
        "bright yellow lemon whole",
        "lemon halved showing juicy flesh",
        "green lime round fresh",
        "lime halved squeezed",
        "lemon and lime together pair",
        "slice of lemon round thin",
    ],
    "other_fruits": [
        "ripe red strawberry single close-up",
        "dragon fruit halved pink flesh white",
        "kiwi fruit halved showing green flesh",
        "peach fuzzy skin whole ripe",
        "plum dark purple glossy ripe",
        "fig fresh halved showing pink inside",
        "jackfruit segment ripe yellow",
        "chikoo sapodilla brown round ripe",
        "star fruit carambola yellow sliced",
        "custard apple sitaphal ripe",
    ],
}

FRUITS_BATCH = [
    "mixed tropical fruit variety flat lay assortment",
    "Indian fruit market variety spread arrangement",
    "all seasonal fruits collection together display",
    "colorful mixed fruits flat lay overhead view",
    "fruit basket overflowing variety mixed",
    "fresh fruit platter assortment mixed cut",
    "mango papaya banana coconut tropical batch",
    "apple orange grapes mixed fruit batch",
    "summer fruit variety arrangement colorful",
    "pomegranate guava chikoo local fruits batch",
    "whole and cut mixed fruit display",
    "fresh fruit vendor arrangement market style",
    "exotic tropical fruit variety collection",
    "citrus fruit variety batch orange lemon lime",
    "berry and small fruit assortment batch",
    "festival fruit offering variety mixed",
    "vitamin C rich fruit variety batch together",
    "ripe colorful fruit flat lay pattern",
    "fruit abundance heap pile mixed",
    "organic farm fruit harvest variety batch",
    "whole fruits only batch arrangement twelve types",
    "cut fruit platter showing inside flesh variety",
    "tropical green fruits batch raw variety",
    "Indian local fruit batch desi variety",
    "premium quality mixed fruit gift basket",
    "rainbow fruit arrangement colorful mix",
    "round shaped fruit collection batch",
    "juicy fruit variety batch close-up",
    "seasonal harvest fruit batch fresh",
    "all Indian fruits together batch collection",
]

FRUIT_CONTEXTS = [
    "whole intact fresh",
    "sliced cross section showing inside flesh",
    "with water droplets fresh",
    "with leaf and stem attached",
    "close-up skin texture macro",
    "top view flat lay",
]

# ─────────────────────────────────────────────────────────────
# 6. VEGETABLES — SINGLE & BATCH
# ─────────────────────────────────────────────────────────────

VEGETABLES_SINGLE = {
    "tomato": [
        "ripe red vine tomato single",
        "tomato halved showing seeds and flesh",
        "bunch of small cherry tomatoes",
        "green raw tomato unripe",
        "roma tomato oval shape",
        "beefsteak tomato large ripe red",
        "yellow tomato ripe variety",
        "heirloom tomato colorful",
    ],
    "onion": [
        "red onion whole round",
        "white onion single whole",
        "onion halved showing layers rings",
        "small shallots pearl onions cluster",
        "green spring onion bunch",
        "onion sliced rings arranged",
        "fresh onion with papery skin",
    ],
    "potato": [
        "brown potato whole russet",
        "yellow potato variety fresh",
        "baby potatoes small cluster",
        "potato halved showing white flesh",
        "sweet potato orange flesh halved",
        "red skin potato variety",
        "purple sweet potato",
    ],
    "brinjal": [
        "purple glossy brinjal eggplant whole",
        "round brinjal variety single",
        "long slim brinjal purple",
        "green brinjal Thai variety",
        "white brinjal variety whole",
        "brinjal halved cross section",
        "small baby brinjals cluster",
    ],
    "okra": [
        "fresh green okra ladyfinger single",
        "okra cluster bunch fresh",
        "okra split showing seeds inside",
        "young tender okra bright green",
        "okra flat lay arrangement",
        "long okra full length",
    ],
    "carrot": [
        "fresh orange carrot whole with top",
        "carrot bunch tied together",
        "carrot halved cross section",
        "baby carrots small bunch",
        "red carrot Indian variety",
        "carrot sliced rounds arranged",
    ],
    "capsicum": [
        "red bell capsicum glossy whole",
        "green capsicum bell pepper whole",
        "yellow capsicum bell pepper",
        "orange capsicum bell pepper",
        "capsicum halved showing seeds",
        "three capsicums mixed colors",
    ],
    "chili": [
        "fresh green chili bunch",
        "red dried chili peppers cluster",
        "long green chili single close-up",
        "red chili fresh whole",
        "small round chili variety",
        "green chili cross section macro",
    ],
    "beans": [
        "green French beans cluster fresh",
        "flat beans variety green",
        "cluster beans guar phali fresh",
        "long beans snake beans fresh",
        "bean pods split showing beans",
        "green beans flat lay",
    ],
    "cucumber": [
        "dark green cucumber whole fresh",
        "cucumber sliced rounds arranged",
        "cucumber halved lengthwise",
        "small pickling cucumber variety",
        "cucumber with flower attached",
        "light green cucumber variety",
    ],
    "pumpkin": [
        "orange pumpkin large whole round",
        "pumpkin halved showing orange flesh seeds",
        "small decorative pumpkin variety",
        "yellow pumpkin variety whole",
        "pumpkin slice wedge cut",
        "green pumpkin raw whole",
    ],
    "other_veggies": [
        "white cauliflower head full",
        "green broccoli floret head",
        "cabbage green head whole",
        "bitter gourd karela textured green",
        "drumstick moringa long pods",
        "colocasia arbi root vegetable",
        "fresh ginger root knobby",
        "turmeric root fresh yellow-orange",
        "garlic bulb whole with cloves",
        "spinach bunch fresh green",
    ],
}

VEGETABLES_BATCH = [
    "mixed vegetable variety flat lay assortment",
    "Indian vegetable market spread all types",
    "all vegetables collection together overhead view",
    "colorful mixed vegetable flat lay",
    "vegetable basket overflowing variety",
    "fresh vegetable platter assortment mixed",
    "root vegetable batch carrot beetroot potato",
    "leafy green vegetable batch spinach cabbage",
    "colorful capsicum tomato brinjal batch",
    "sabzi mandi vegetable vendor arrangement",
    "whole vegetables only batch twelve types",
    "cut vegetable batch showing inside flesh",
    "green vegetable variety batch fresh",
    "Indian curry vegetable batch mix",
    "organic farm fresh harvest variety batch",
    "market fresh daily vegetable batch mix",
    "rainbow vegetable arrangement colorful",
    "seasonal vegetable abundance heap pile",
    "chili onion tomato garlic cooking base batch",
    "mixed vegetable stir-fry variety raw batch",
    "gourd variety batch pumpkin cucumber bitter",
    "onion tomato capsicum peppers batch together",
    "beans variety batch cluster long flat",
    "fresh herb vegetable batch coriander mint",
    "village fresh vegetable harvest variety",
    "premium quality vegetable basket",
    "north Indian vegetable batch assortment",
    "south Indian vegetable batch traditional",
    "tropical vegetable variety batch",
    "all Indian vegetables together batch collection",
]

VEG_CONTEXTS = [
    "whole fresh intact",
    "sliced cross section showing inside",
    "with water droplets fresh",
    "with stem and leaf attached",
    "close-up skin texture macro",
    "top view flat lay surface",
]

# ─────────────────────────────────────────────────────────────
# 7. COOL DRINKS & BEVERAGES
# ─────────────────────────────────────────────────────────────

COOL_DRINKS = {
    "mojito": [
        "classic mint mojito with crushed ice and lime",
        "strawberry mojito pink color with mint",
        "mango mojito yellow with fresh mint",
        "virgin mojito clear with lime wedge",
        "lychee mojito with mint garnish",
        "passion fruit mojito tropical",
        "watermelon mojito fresh red",
        "blue curacao mojito layered blue",
        "coconut mojito creamy white",
        "blackberry mojito dark purple",
    ],
    "lemon_soda": [
        "fresh lime soda clear fizzy with lemon slice",
        "masala lemon soda Indian spiced",
        "sweet lemon soda with ice",
        "salty lemon soda Indian style",
        "lemon soda with mint leaves",
        "nimbu pani lemon water fresh",
        "sparkling lemon water with bubbles",
        "lemon soda with black salt masala",
        "chilled lemon soda condensation on glass",
        "lemon soda with ice cubes tall glass",
    ],
    "lassi": [
        "thick sweet mango lassi in brass glass",
        "plain sweet white lassi frothy",
        "salted lassi Indian yogurt drink",
        "rose flavored pink lassi",
        "strawberry lassi pink frothy",
        "saffron kesar lassi golden yellow",
        "thick creamy Punjabi lassi full glass",
        "blueberry lassi purple color",
        "lassi with malai cream on top",
        "traditional clay pot lassi earthen",
    ],
    "tender_coconut": [
        "green tender coconut whole with straw",
        "tender coconut on white surface fresh",
        "tender coconut water poured in glass",
        "coconut with colorful paper straw",
        "two tender coconuts together with straws",
        "tender coconut cut open showing jelly",
        "tender coconut with spoon and straw",
        "young green coconut single fresh",
        "tender coconut organic fresh natural",
        "tender coconut summer refreshing",
    ],
    "fresh_juice": [
        "fresh orange juice glass with orange slice",
        "carrot juice orange in glass",
        "sugarcane juice fresh pressed in glass",
        "pomegranate juice deep red in glass",
        "watermelon juice pink red refreshing",
        "mosambi sweet lime juice fresh",
        "pineapple juice yellow with pineapple",
        "mixed fruit juice colorful in glass",
        "beetroot carrot juice healthy dark red",
        "green apple juice clear pale in glass",
    ],
    "buttermilk": [
        "chilled Indian buttermilk chaas in glass",
        "spiced masala buttermilk with curry leaves",
        "white buttermilk in traditional brass tumbler",
        "frothy fresh buttermilk plain",
        "tadka buttermilk with mustard seeds",
        "South Indian neer mor diluted buttermilk",
        "buttermilk with coriander garnish",
        "chilled chaas with ice cubes summer",
        "traditional clay pot buttermilk mitti",
        "buttermilk pitcher with poured glass",
    ],
}

DRINK_VESSELS = [
    "in tall clear glass with ice",
    "in traditional brass tumbler",
    "in clay kulhad earthen cup",
    "in mason jar glass",
    "in tall plastic cup with straw",
    "in ceramic mug with saucer",
]

DRINK_DETAILS = [
    "condensation droplets on cold glass",
    "garnished with fresh mint leaves on top",
    "with colorful paper straw inserted",
    "ice cubes visible inside drink",
    "garnish of fruit slice on rim",
]

# ─────────────────────────────────────────────────────────────
# 8. INDIAN FOODS
# ─────────────────────────────────────────────────────────────

INDIAN_FOODS = {
    "biryani": [
        "Hyderabadi dum biryani with chicken leg piece",
        "Dindigul thalappakatti mutton biryani",
        "Ambur star biryani seeraga samba rice",
        "Malabar chicken biryani coconut",
        "Kolkata biryani with potato and egg",
        "Lucknowi awadhi dum biryani",
        "Chettinad biryani spicy aromatic",
        "Kashmiri biryani with saffron dry fruits",
        "egg biryani golden fried eggs",
        "vegetable biryani aromatic basmati",
    ],
    "dosa": [
        "golden crispy masala dosa with potato filling",
        "paper thin ghee roast dosa browned",
        "fluffy soft set dosa stack",
        "lacy rava dosa with onion",
        "delicate neer dosa white thin",
        "pesarattu green dosa moong",
        "egg dosa spicy with onion",
        "cheese dosa melted inside",
        "onion tomato uthappam thick",
        "crispy paper dosa very thin large",
    ],
    "idly": [
        "soft white idly stack with sambar",
        "mini idly small bite size",
        "kanchipuram idly thick spiced",
        "tatte idly large flat Karnataka",
        "rava idly with mustard seeds",
        "brown rice idly healthy",
        "idly with coconut chutney",
        "idly with tomato chutney red",
        "idly podi powder sesame oil",
        "steamed idly fresh from vessel",
    ],
    "parotta": [
        "layered flaky Kerala parotta crispy",
        "coin parotta small round pieces",
        "egg parotta wrapped with egg",
        "kothu parotta minced shredded spicy",
        "srilankan parotta layered fluffy",
        "Malabar parotta soft flaky layers",
        "parotta with chicken salna side",
        "parotta with kurma curry side",
        "fresh hot parotta from tawa",
        "parotta stack layers visible",
    ],
    "curry": [
        "creamy rich butter chicken gravy red",
        "spicy Chettinad chicken curry dark",
        "Kerala fish curry coconut milk red",
        "mutton rogan josh dark red aromatic",
        "egg curry South Indian style",
        "prawn masala in thick gravy",
        "crab masala spicy dark",
        "chicken tikka masala red gravy",
        "goat curry with bone-in pieces",
        "fish fry Chettinad style spiced",
    ],
    "rice_dishes": [
        "lemon rice South Indian yellow",
        "curd rice with pomegranate",
        "tomato rice spicy red",
        "sambar rice mixed together",
        "pongal creamy rice lentil dish",
        "tamarind rice Puliyodharai",
        "ghee rice fragrant basmati",
        "coconut milk rice Thengai Sadham",
        "jeera rice cumin basmati",
        "plain steam rice with ghee",
    ],
    "snacks": [
        "crispy golden samosa three pieces",
        "medu vada with hole South Indian",
        "crispy murukku coil shaped",
        "pakora bhaji onion fritters",
        "bread pakora stuffed fried",
        "aloo tikki pan fried patty",
        "masala vada crispy South Indian",
        "crispy bajji chili fritters",
        "ribbon pakoda flat fried snack",
        "tapioca chips banana chips batch",
    ],
    "sweets": [
        "syrup soaked gulab jamun",
        "ghee dripping mysore pak golden",
        "crispy orange jalebi fresh",
        "rava kesari South Indian saffron",
        "round besan ladoo",
        "halwa carrot gajar Indian",
        "kaju katli diamond cut silver",
        "rasgulla spongy white",
        "creamy rice kheer bowl",
        "coconut burfi white square",
    ],
}

INDIAN_FOOD_VESSELS = [
    "in traditional banana leaf plate",
    "in round steel thali plate",
    "in ceramic bowl garnished",
    "in rustic clay pot",
    "in copper serving bowl",
    "in terracotta plate",
]

INDIAN_FOOD_STYLES = [
    "South Indian restaurant style plating",
    "authentic home style serving",
    "dhaba roadside style presentation",
    "wedding feast grand serving",
    "street food casual style",
]

# ─────────────────────────────────────────────────────────────
# 9. WORLD FOODS
# ─────────────────────────────────────────────────────────────

WORLD_FOODS = {
    "pizza": [
        "Margherita pizza with fresh basil mozzarella",
        "deep dish pepperoni pizza cheese pull",
        "BBQ chicken pizza loaded toppings",
        "four cheese pizza melted golden",
        "veggie supreme pizza bell peppers",
        "spicy chicken pizza with jalapenos",
        "paneer tikka pizza Indian fusion",
        "mushroom truffle pizza gourmet",
        "pizza slice triangular single serving",
        "mini personal pizza individual size",
        "pizza with tomato sauce base visible",
        "charred crust artisan pizza rustic",
    ],
    "burger": [
        "juicy beef cheeseburger melting cheddar",
        "crispy fried chicken burger coleslaw",
        "smoky BBQ double patty burger",
        "mushroom Swiss burger grilled patty",
        "spicy chicken burger with sauce",
        "veggie bean burger with avocado",
        "smash burger caramelized onions",
        "fish burger tartar sauce lettuce",
        "egg burger with sunny side up",
        "burger halved showing layers cross section",
        "mini slider burgers three pieces",
        "paneer tikka burger Indian style",
    ],
    "fried_chicken": [
        "crispy golden fried chicken piece drumstick",
        "KFC style fried chicken breast piece",
        "boneless crispy fried chicken strips",
        "buttermilk fried chicken golden brown",
        "spicy fried chicken Indian masala style",
        "fried chicken bucket full pieces",
        "fried chicken sandwich in bun",
        "popcorn chicken bite size pieces",
        "Korean crispy fried chicken glazed",
        "fried chicken with honey sauce drizzle",
        "double fried extra crispy chicken",
        "fried chicken platter with dips",
    ],
    "french_fries": [
        "crispy golden French fries in serving box",
        "thin shoestring fries tall glass cup",
        "thick cut steak fries golden",
        "curly fries spiral crispy",
        "waffle fries grid pattern crispy",
        "loaded cheese fries with sauce",
        "sweet potato fries orange crispy",
        "chili cheese fries loaded",
        "garlic parmesan fries seasoned",
        "French fries in paper cone",
        "seasoned spicy masala fries",
        "truffle oil fries gourmet style",
    ],
    "noodles": [
        "wok tossed vegetable noodles Chinese style",
        "spicy Schezwan noodles red sauce",
        "hakka noodles egg Indian Chinese",
        "ramen bowl with egg and toppings",
        "pad thai noodles Thai style",
        "chow mein stir fried noodles",
        "Maggi instant noodles Indian style",
        "glass noodles transparent Korean",
        "udon noodles thick Japanese soup",
        "drunken noodles flat rice noodles",
        "crispy noodles base with sauce",
        "lo mein noodles soft Chinese",
    ],
    "fried_rice": [
        "wok fried rice with egg vegetables",
        "chicken fried rice Chinese style",
        "Schezwan fried rice spicy red",
        "egg fried rice golden",
        "shrimp fried rice seafood",
        "pineapple fried rice Thai style",
        "kimchi fried rice Korean style",
        "vegetable fried rice colorful",
        "Indian Chinese fried rice masala",
        "garlic butter fried rice",
        "black pepper fried rice dark seasoned",
        "restaurant quality fried rice plated",
    ],
    "chinese": [
        "steaming dim sum bamboo basket",
        "crispy spring rolls golden fried",
        "orange chicken with sesame seeds",
        "chicken manchurian in dark sauce",
        "gobi manchurian cauliflower Indian Chinese",
        "hot and sour soup bowl",
        "wonton soup with floating dumplings",
        "Peking duck sliced with pancakes",
        "kung pao chicken with peanuts",
        "sweet and sour pork dish colorful",
        "mapo tofu spicy red sauce",
        "steamed har gow prawn dumplings",
    ],
}

WORLD_FOOD_VESSELS = [
    "on white ceramic dinner plate",
    "on rustic wooden serving board",
    "in deep ceramic bowl",
    "on dark slate serving board",
    "in cast iron skillet hot",
    "in red and white paper box",
    "in bamboo basket steamed",
]

WORLD_FOOD_ANGLES = [
    "close-up food photography macro",
    "overhead flat lay food shot",
    "angled hero shot 45 degree",
    "side view plated professional",
    "front view restaurant style",
]

# ─────────────────────────────────────────────────────────────
# 10. FOOTWEAR
# ─────────────────────────────────────────────────────────────

FOOTWEAR = {
    "chappals": [
        "brown leather kolhapuri chappal flat",
        "rubber flip flop slipper casual",
        "simple hawai chappal rubber traditional",
        "embroidered Rajasthani chappal colorful",
        "black rubber home slipper foam",
        "leather sole flat chappal simple",
        "wooden paduka traditional Indian",
        "multi-color fabric chappal",
        "synthetic chappal flat casual",
        "thong sandal rubber flat",
    ],
    "sandals": [
        "leather gladiator sandal brown straps",
        "sports sandal with velcro strap",
        "platform sandal women fashion",
        "strappy heeled sandal elegant",
        "beach sandal waterproof",
        "toe ring sandal Indian style",
        "backstrap sandal comfortable",
        "wedge cork sandal women",
        "casual flat sandal summer",
        "ankle strap heeled sandal fashion",
    ],
    "shoes": [
        "black Oxford leather shoes polished formal",
        "brown Derby brogue leather shoes",
        "casual white canvas shoes",
        "loafer shoes tan leather slip on",
        "boat shoes leather casual",
        "Derby shoes dark brown",
        "monk strap shoes burgundy",
        "smart casual leather shoes black",
        "formal lace-up shoes office",
        "brogues detailed perforations",
    ],
    "heels": [
        "pointed toe stiletto heels black",
        "block heel court shoes nude",
        "strappy heeled sandal evening",
        "platform pump heel women",
        "kitten heel subtle women",
        "wedge heel casual women",
        "ankle boot low heel women",
        "embellished party heel rhinestone",
        "spool heel classic women",
        "tapered medium heel office women",
    ],
    "sports_shoes": [
        "white Nike running shoes",
        "Adidas ultraboost sports shoes",
        "Skechers walking shoes comfort",
        "Puma training shoes colorful",
        "New Balance running shoes grey",
        "Reebok gym training shoes",
        "badminton shoes indoor court",
        "football turf shoes studs",
        "cricket shoes rubber studs white",
        "basketball shoes high top",
    ],
    "kids_footwear": [
        "kids school shoes black leather",
        "colorful children sneakers velcro",
        "kids sandal soft sole",
        "toddler shoes soft pink",
        "children sports shoes colorful",
        "baby shoes tiny first steps",
    ],
}

SHOE_VIEWS = [
    "side profile single shoe view",
    "pair from front angled 3/4 view",
    "sole detail underside view",
    "top view flat lay overhead",
    "heel detail close-up macro",
    "45 degree hero shot pair",
]

SHOE_DETAILS = [
    "clean pristine condition",
    "leather texture visible close-up",
    "stitch detail macro view",
    "lace detail close-up",
    "sole grip pattern detail",
]

# ─────────────────────────────────────────────────────────────
# 11. INDIAN DRESS
# ─────────────────────────────────────────────────────────────

INDIAN_DRESS = {
    "saree": [
        "Kanchipuram silk saree gold zari border folded",
        "Banarasi silk saree rich brocade work",
        "cotton saree casual lightweight",
        "South Indian silk saree traditional",
        "Mysore silk saree smooth texture",
        "chiffon saree transparent lightweight",
        "net saree embroidered festive",
        "bridal saree heavy embroidery gold",
        "Kerala kasavu cream gold border saree",
        "Bandhani tie-dye Rajasthani saree",
        "chanderi cotton silk saree",
        "patola Gujarati weave saree",
    ],
    "salwar_kameez": [
        "embroidered salwar kameez festive",
        "Anarkali suit long flared dress",
        "straight cut simple salwar suit",
        "palazzo suit flared pants",
        "patiala salwar traditional Punjab",
        "cotton salwar kameez summer",
        "silk salwar kameez party wear",
        "churidar salwar kameez tight",
        "printed salwar kameez floral",
        "designer salwar kameez modern",
    ],
    "lehenga": [
        "bridal lehenga choli heavy embroidery",
        "flared lehenga skirt festive wear",
        "half saree lehenga South Indian",
        "ghagra choli Rajasthani folk",
        "lehenga with crop top modern",
        "pink bridal lehenga traditional",
    ],
    "kurta": [
        "men kurta white cotton simple",
        "kurta pajama set Indian traditional",
        "embroidered kurta festive occasion",
        "nehru collar kurta elegant",
        "short kurta casual modern",
        "silk kurta festive golden",
        "linen kurta summer lightweight",
        "sherwani men wedding formal",
        "pathani suit men traditional",
        "printed kurta modern design",
    ],
    "kids_dress": [
        "children lehenga choli girls festive",
        "kids kurta pajama boys traditional",
        "baby girl frock Indian style",
        "kids school uniform formal",
        "boys sherwani kids wedding",
        "girls half saree South Indian kids",
        "boys dhoti kurta traditional",
        "girls salwar kameez party wear",
        "kids ethnic wear accessories",
        "infant Indian traditional dress",
    ],
}

DRESS_CONTEXTS = [
    "neatly folded showing fabric",
    "draped showing full fabric flow",
    "flat lay full garment overhead",
    "hanging on display showing full length",
    "close-up fabric embroidery texture detail",
    "saree pleats detail close-up",
]

DRESS_STYLE = [
    "fashion product photography",
    "textile studio photography",
    "ethnic wear catalog photography",
    "traditional garment editorial photography",
]

# ─────────────────────────────────────────────────────────────
# 12. JEWELLERY MODELS
# ─────────────────────────────────────────────────────────────

JEWELLERY_MODELS = {
    "gold_necklace_models": [
        "beautiful Indian woman wearing heavy gold temple necklace",
        "South Indian woman with traditional layered gold haar necklace",
        "young Indian woman with gold chain necklace portrait",
        "woman wearing gold Lakshmi coin necklace traditional",
        "Indian girl with gold rani haar long necklace",
        "Tamil woman with gold kasumala necklace",
        "woman wearing bridal gold necklace set heavy",
        "Indian woman with antique gold choker necklace",
        "woman wearing gold mangalsutra chain",
        "lady with kundan polki necklace traditional",
    ],
    "bridal_models": [
        "beautiful South Indian bride full gold jewellery set",
        "North Indian bride with gold and kundan bridal set",
        "Tamil bride with temple jewellery complete set",
        "Punjabi bride with chooda and gold bridal jewelry",
        "Rajasthani bride with traditional gold silver jewellery",
        "Bengali bride with gold Shakha Pola bangles",
        "Maharashtrian bride with Nath Necklace green bangles",
        "Kerala bride gold mango mala necklace kasavu saree",
        "Kannada bride traditional gold set",
        "bridal close-up face portrait with gold maang tikka",
    ],
    "earring_models": [
        "Indian woman with gold jhumka bell earrings",
        "girl wearing gold hoop earrings Indian",
        "woman with gold chandbali crescent earrings",
        "Indian girl with long gold chandelier earrings",
        "woman wearing large gold earrings portrait",
        "South Indian woman with gold kammal earrings",
        "girl with diamond and gold stud earrings",
        "young woman gold drop earrings portrait",
    ],
    "bangle_models": [
        "woman hands with full gold bangles set",
        "Indian woman wearing gold kaada bangle",
        "bridal hands with gold and stone bangles",
        "woman wearing mixed glass and gold bangles",
        "South Indian woman gold valaiyal bangles",
        "hands decorated with henna and gold bangles",
        "woman with green glass bangles and gold",
        "girl with gold bracelet chain wrist",
    ],
}

MODEL_LOOKS = [
    "elegant formal pose studio",
    "natural smile happy expression",
    "side profile graceful pose",
    "three quarter face portrait pose",
    "looking down jewelry focus",
    "close-up portrait glowing skin",
]

MODEL_SAREE = [
    "wearing Kanchipuram silk saree",
    "in Banarasi silk bridal saree",
    "in traditional South Indian saree",
    "in bridal red silk saree",
]

# ─────────────────────────────────────────────────────────────
# 13. OFFICE & FASHION MODELS
# ─────────────────────────────────────────────────────────────

OFFICE_MODELS = {
    "women_office": [
        "professional Indian woman in formal white shirt and trousers",
        "businesswoman in navy blue blazer and skirt",
        "corporate woman in formal pant suit grey",
        "office woman in saree formal work style",
        "professional woman in kurta and pants formal",
        "Indian businesswoman in black formal suit",
        "working woman in formal dress midi",
        "office woman in printed formal blouse",
        "young professional woman corporate attire",
        "woman in formal blazer with portfolio",
    ],
    "men_formal": [
        "Indian man in formal white shirt and black trousers",
        "businessman in navy blue suit and tie",
        "professional man in grey formal suit",
        "office man in formal kurta pajama",
        "corporate man in black suit white shirt",
        "young professional man blazer and chinos",
        "man in formal shirt and tie portrait",
        "businessman in dark suit confident pose",
        "professional Indian man formal attire",
        "man in crisp formal shirt office look",
    ],
    "casual_smart": [
        "Indian woman in smart casual kurta jeans",
        "woman in floral printed western top skirt",
        "girl in smart casual dress modern Indian",
        "woman in simple salwar kameez casual",
        "lady in linen shirt and trousers smart",
        "young woman in smart western formal",
        "woman in traditional with modern fusion wear",
        "girl in chic casual Indian office wear",
    ],
}

MODEL_POSES_OFFICE = [
    "confident standing front view portrait",
    "side profile elegant posture",
    "three quarter body view",
    "arms crossed professional pose",
    "natural smile relaxed portrait",
    "close-up portrait professional headshot style",
]

# ─────────────────────────────────────────────────────────────
# PROMPT ENGINE CLASS
# ─────────────────────────────────────────────────────────────

class PromptEngine:
    def __init__(self):
        self.generated_prompts = set()

    def make_prompt(self, subject, extra=""):
        angle   = random.choice(CAMERA_ANGLES)
        light   = random.choice(LIGHTING_STYLES)
        quality = random.choice(DETAIL_QUALITY)
        style   = random.choice(PHOTO_STYLES)
        parts = [subject]
        if extra:
            parts.append(extra)
        parts.extend([angle, light, quality, style, BASE_SUFFIX])
        return ", ".join(parts)

    def make_animal_prompt(self, subject, extra=""):
        light   = random.choice(LIGHTING_STYLES)
        quality = random.choice(DETAIL_QUALITY)
        parts = [subject]
        if extra:
            parts.append(extra)
        parts.extend([light, quality, ANIMAL_SUFFIX])
        return ", ".join(parts)

    def make_model_prompt(self, subject, extra=""):
        light   = random.choice(LIGHTING_STYLES)
        quality = random.choice(DETAIL_QUALITY)
        parts = [subject]
        if extra:
            parts.append(extra)
        parts.extend([light, quality, MODEL_SUFFIX])
        return ", ".join(parts)

    # ── 1. LIVE POULTRY & ANIMALS ────────────────────────────
    def generate_poultry_animal_prompts(self):
        prompts = []

        for breed in ROOSTER["breeds"]:
            for pose in ROOSTER["poses"]:
                detail = random.choice(ROOSTER["details"])
                p = self.make_animal_prompt(f"{breed}, {pose}", detail)
                prompts.append({"category": "poultry_animals", "subcategory": "rooster",
                                 "prompt": p, "seed": random.randint(1, 999999)})

        for t in BROILER_CHICKEN["types"]:
            for pose in BROILER_CHICKEN["poses"]:
                detail = random.choice(BROILER_CHICKEN["details"])
                p = self.make_animal_prompt(f"{t}, {pose}", detail)
                prompts.append({"category": "poultry_animals", "subcategory": "broiler_chicken",
                                 "prompt": p, "seed": random.randint(1, 999999)})

        for t in GOAT["types"]:
            for pose in GOAT["poses"]:
                detail = random.choice(GOAT["details"])
                p = self.make_animal_prompt(f"{t}, {pose}", detail)
                prompts.append({"category": "poultry_animals", "subcategory": "goat",
                                 "prompt": p, "seed": random.randint(1, 999999)})

        for t in QUAIL["types"]:
            for pose in QUAIL["poses"]:
                detail = random.choice(QUAIL["details"])
                p = self.make_animal_prompt(f"{t}, {pose}", detail)
                prompts.append({"category": "poultry_animals", "subcategory": "quail",
                                 "prompt": p, "seed": random.randint(1, 999999)})

        for t in COW["types"]:
            for pose in COW["poses"]:
                detail = random.choice(COW["details"])
                p = self.make_animal_prompt(f"{t}, {pose}", detail)
                prompts.append({"category": "poultry_animals", "subcategory": "cow",
                                 "prompt": p, "seed": random.randint(1, 999999)})

        return prompts

    # ── 2. RAW MEAT & EGGS ───────────────────────────────────
    def generate_raw_meat_prompts(self):
        prompts = []

        for cut in RAW_CHICKEN_MEAT["cuts"]:
            for pres in RAW_CHICKEN_MEAT["presentation"]:
                detail = random.choice(RAW_CHICKEN_MEAT["details"])
                style  = random.choice(MEAT_STYLE)
                p = self.make_prompt(f"{cut}, {pres}", f"{detail}, {style}")
                prompts.append({"category": "raw_meat", "subcategory": "raw_chicken",
                                 "prompt": p, "seed": random.randint(1, 999999)})

        for cut in RAW_GOAT_MEAT["cuts"]:
            for pres in RAW_GOAT_MEAT["presentation"]:
                detail = random.choice(RAW_GOAT_MEAT["details"])
                style  = random.choice(MEAT_STYLE)
                p = self.make_prompt(f"{cut}, {pres}", f"{detail}, {style}")
                prompts.append({"category": "raw_meat", "subcategory": "raw_goat",
                                 "prompt": p, "seed": random.randint(1, 999999)})

        for cut in RAW_QUAIL_MEAT["cuts"]:
            for pres in RAW_QUAIL_MEAT["presentation"]:
                detail = random.choice(RAW_QUAIL_MEAT["details"])
                style  = random.choice(MEAT_STYLE)
                p = self.make_prompt(f"{cut}, {pres}", f"{detail}, {style}")
                prompts.append({"category": "raw_meat", "subcategory": "raw_quail",
                                 "prompt": p, "seed": random.randint(1, 999999)})

        for egg in EGGS["types"]:
            for pres in EGGS["presentation"]:
                detail = random.choice(EGGS["details"])
                p = self.make_prompt(f"{egg}, {pres}", detail)
                prompts.append({"category": "raw_meat", "subcategory": "eggs",
                                 "prompt": p, "seed": random.randint(1, 999999)})

        return prompts

    # ── 3. VEHICLES ──────────────────────────────────────────
    def generate_vehicle_prompts(self):
        prompts = []

        for car_type, models in INDIAN_CARS.items():
            for model in models:
                for angle in CAR_ANGLES_V:
                    detail = random.choice(CAR_DETAILS)
                    p = self.make_prompt(f"{model}, {angle}", detail)
                    prompts.append({"category": "vehicles", "subcategory": f"indian_cars_{car_type}",
                                     "prompt": p, "seed": random.randint(1, 999999)})

        for bike_type, models in INDIAN_BIKES.items():
            for model in models:
                for angle in CAR_ANGLES_V:
                    detail = random.choice(CAR_DETAILS)
                    p = self.make_prompt(f"{model}, {angle}", detail)
                    prompts.append({"category": "vehicles", "subcategory": f"bikes_{bike_type}",
                                     "prompt": p, "seed": random.randint(1, 999999)})

        for auto in AUTO_RICKSHAW["types"]:
            for angle in AUTO_RICKSHAW["angles"]:
                detail = random.choice(AUTO_RICKSHAW["details"])
                p = self.make_prompt(f"{auto}, {angle}", detail)
                prompts.append({"category": "vehicles", "subcategory": "auto_rickshaw",
                                 "prompt": p, "seed": random.randint(1, 999999)})

        return prompts

    # ── 4. FLOWERS ───────────────────────────────────────────
    def generate_flower_prompts(self):
        prompts = []

        for flower_type, varieties in FLOWERS_SINGLE.items():
            for variety in varieties:
                for stage in FLOWER_STAGES:
                    for context in FLOWER_CONTEXTS:
                        approach = random.choice(FLOWER_PHOTO)
                        subject = f"{variety}, {stage}, {context}, {approach}"
                        p = self.make_prompt(subject)
                        prompts.append({"category": "flowers", "subcategory": f"single_{flower_type}",
                                         "prompt": p, "seed": random.randint(1, 999999)})

        for batch in FLOWERS_BATCH:
            for approach in FLOWER_PHOTO:
                p = self.make_prompt(batch, approach)
                prompts.append({"category": "flowers", "subcategory": "batch_flowers",
                                 "prompt": p, "seed": random.randint(1, 999999)})

        return prompts

    # ── 5. FRUITS ────────────────────────────────────────────
    def generate_fruit_prompts(self):
        prompts = []
        batch_styles = ["overhead flat lay photography", "studio product photography",
                         "natural light photography", "editorial food photography"]

        for fruit_type, fruits in FRUITS_SINGLE.items():
            for fruit in fruits:
                for context in FRUIT_CONTEXTS:
                    p = self.make_prompt(f"{fruit}, {context}")
                    prompts.append({"category": "fruits", "subcategory": f"single_{fruit_type}",
                                     "prompt": p, "seed": random.randint(1, 999999)})

        for batch in FRUITS_BATCH:
            for style in batch_styles:
                p = self.make_prompt(batch, style)
                prompts.append({"category": "fruits", "subcategory": "batch_all_fruits",
                                 "prompt": p, "seed": random.randint(1, 999999)})

        return prompts

    # ── 6. VEGETABLES ────────────────────────────────────────
    def generate_vegetable_prompts(self):
        prompts = []
        batch_styles = ["overhead flat lay photography", "studio product photography",
                         "natural light photography", "editorial food photography"]

        for veg_type, vegs in VEGETABLES_SINGLE.items():
            for veg in vegs:
                for context in VEG_CONTEXTS:
                    p = self.make_prompt(f"{veg}, {context}")
                    prompts.append({"category": "vegetables", "subcategory": f"single_{veg_type}",
                                     "prompt": p, "seed": random.randint(1, 999999)})

        for batch in VEGETABLES_BATCH:
            for style in batch_styles:
                p = self.make_prompt(batch, style)
                prompts.append({"category": "vegetables", "subcategory": "batch_all_vegetables",
                                 "prompt": p, "seed": random.randint(1, 999999)})

        return prompts

    # ── 7. COOL DRINKS ───────────────────────────────────────
    def generate_drink_prompts(self):
        prompts = []

        for drink_type, drinks in COOL_DRINKS.items():
            for drink in drinks:
                for vessel in DRINK_VESSELS:
                    detail = random.choice(DRINK_DETAILS)
                    p = self.make_prompt(f"{drink}, {vessel}", f"{detail}, beverage photography")
                    prompts.append({"category": "cool_drinks", "subcategory": drink_type,
                                     "prompt": p, "seed": random.randint(1, 999999)})

        return prompts

    # ── 8. INDIAN FOODS ──────────────────────────────────────
    def generate_indian_food_prompts(self):
        prompts = []
        angles = ["close-up overhead flat lay", "angled hero shot",
                  "side view", "front view restaurant style"]

        for food_type, dishes in INDIAN_FOODS.items():
            for dish in dishes:
                for vessel in INDIAN_FOOD_VESSELS:
                    style = random.choice(INDIAN_FOOD_STYLES)
                    angle = random.choice(angles)
                    p = self.make_prompt(f"{dish}, {vessel}", f"{style}, {angle}")
                    prompts.append({"category": "indian_foods", "subcategory": food_type,
                                     "prompt": p, "seed": random.randint(1, 999999)})

        return prompts

    # ── 9. WORLD FOODS ───────────────────────────────────────
    def generate_world_food_prompts(self):
        prompts = []

        for food_type, items in WORLD_FOODS.items():
            for item in items:
                for vessel in WORLD_FOOD_VESSELS:
                    angle = random.choice(WORLD_FOOD_ANGLES)
                    p = self.make_prompt(f"{item}, {vessel}", f"{angle}, restaurant quality")
                    prompts.append({"category": "world_foods", "subcategory": food_type,
                                     "prompt": p, "seed": random.randint(1, 999999)})

        return prompts

    # ── 10. FOOTWEAR ─────────────────────────────────────────
    def generate_footwear_prompts(self):
        prompts = []

        for shoe_type, shoes in FOOTWEAR.items():
            for shoe in shoes:
                for view in SHOE_VIEWS:
                    detail = random.choice(SHOE_DETAILS)
                    p = self.make_prompt(f"{shoe}, {view}", f"{detail}, footwear product photography")
                    prompts.append({"category": "footwear", "subcategory": shoe_type,
                                     "prompt": p, "seed": random.randint(1, 999999)})

        return prompts

    # ── 11. INDIAN DRESS ─────────────────────────────────────
    def generate_dress_prompts(self):
        prompts = []

        for dress_type, garments in INDIAN_DRESS.items():
            for garment in garments:
                for context in DRESS_CONTEXTS:
                    style = random.choice(DRESS_STYLE)
                    p = self.make_prompt(f"{garment}, {context}", style)
                    prompts.append({"category": "indian_dress", "subcategory": dress_type,
                                     "prompt": p, "seed": random.randint(1, 999999)})

        return prompts

    # ── 12. JEWELLERY MODELS ─────────────────────────────────
    def generate_jewellery_model_prompts(self):
        prompts = []

        for model_type, models in JEWELLERY_MODELS.items():
            for model in models:
                for look in MODEL_LOOKS:
                    saree = random.choice(MODEL_SAREE)
                    p = self.make_model_prompt(f"{model}, {saree}, {look}")
                    prompts.append({"category": "jewellery_models", "subcategory": model_type,
                                     "prompt": p, "seed": random.randint(1, 999999)})

        return prompts

    # ── 13. OFFICE MODELS ────────────────────────────────────
    def generate_office_model_prompts(self):
        prompts = []

        for model_type, models in OFFICE_MODELS.items():
            for model in models:
                for pose in MODEL_POSES_OFFICE:
                    p = self.make_model_prompt(f"{model}, {pose}")
                    prompts.append({"category": "office_models", "subcategory": model_type,
                                     "prompt": p, "seed": random.randint(1, 999999)})

        return prompts

    # ═══════════════════════════════════════════════════════════
    # GENERATE ALL
    # ═══════════════════════════════════════════════════════════

    def generate_all_prompts(self):
        print("🎨 Generating all prompts — Guru Image Usha PNG Library V3")
        print("=" * 60)
        all_prompts = []

        generators = [
            ("Live Poultry & Animals",    self.generate_poultry_animal_prompts),
            ("Raw Meat & Eggs",           self.generate_raw_meat_prompts),
            ("Vehicles (Indian)",         self.generate_vehicle_prompts),
            ("Flowers (Single + Batch)",  self.generate_flower_prompts),
            ("Fruits (Single + Batch)",   self.generate_fruit_prompts),
            ("Vegetables (Single+Batch)", self.generate_vegetable_prompts),
            ("Cool Drinks",               self.generate_drink_prompts),
            ("Indian Foods",              self.generate_indian_food_prompts),
            ("World Foods",               self.generate_world_food_prompts),
            ("Footwear",                  self.generate_footwear_prompts),
            ("Indian Dress",              self.generate_dress_prompts),
            ("Jewellery Models",          self.generate_jewellery_model_prompts),
            ("Office Models",             self.generate_office_model_prompts),
        ]

        category_counts = {}
        for name, gen_func in generators:
            prev = len(all_prompts)
            all_prompts.extend(gen_func())
            count = len(all_prompts) - prev
            category_counts[name] = count
            print(f"  ✅ {name}: {count} prompts")

        # Seed multiplier — double all prompts with micro variation
        micro_variations = [
            "extremely detailed surface texture",
            "ultra sharp tack focus",
            "fine grain material detail visible",
            "crisp clean photographic quality",
            "true to life color accuracy",
            "lifelike ultra realistic render",
        ]
        extended = []
        for item in all_prompts:
            extended.append(item)
            new_item = dict(item)
            new_item["prompt"] = item["prompt"] + f", {random.choice(micro_variations)}"
            new_item["seed"] = random.randint(100000, 999999)
            extended.append(new_item)

        all_prompts = extended
        print(f"\n  🔁 After seed-multiplier: {len(all_prompts)} total unique prompts")

        random.shuffle(all_prompts)

        for i, p in enumerate(all_prompts):
            p["index"] = i
            p["filename"] = f"img_{i:06d}.png"
            p["status"] = "pending"

        print(f"\n🎯 TOTAL PROMPTS GENERATED: {len(all_prompts)}")
        print("\n📊 Category Summary (base × 2 with seed multiplier):")
        for name, count in category_counts.items():
            print(f"   {name:35s}: {count:5d} base → {count*2:5d} total")

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
            print(f"  💾 {cat}.json  →  {len(items)} prompts  ({size_kb:.1f} KB)")

        index = {
            "total": len(prompts),
            "categories": list(by_cat.keys()),
            "files": [f"{c}.json" for c in by_cat],
        }
        with open(out / "index.json", "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2, ensure_ascii=False)

        print(f"\n✅ Saved {len(prompts)} prompts across {len(by_cat)} categories in '{output_dir}/'")
        return output_dir


def load_all_prompts(splits_dir="prompts/splits"):
    splits = Path(splits_dir)
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

    print(f"📦 Loaded {len(all_prompts)} prompts from {len(files)} split files.")
    return all_prompts


if __name__ == "__main__":
    engine = PromptEngine()
    engine.save_prompts("prompts/splits")
