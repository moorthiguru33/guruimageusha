"""
🎨 PNG Library - World-Class Ultra-Realistic Prompt Engine V2
Generates 80,000+ UNIQUE prompts using combinatorial logic
100% Photorealistic | Solid Light Grey Background | No Cartoon/Illustration
Every image will be different - guaranteed!
"""

import random
import json
from pathlib import Path

# ─────────────────────────────────────────────
# MASTER PROMPT FORMULA (Ultra-Realistic Photography)
# ─────────────────────────────────────────────
# Key principles:
#   1. NO conflicting styles (no "watercolor + photorealistic")
#   2. Real camera + lens references (FLUX responds strongly)
#   3. Solid light grey background (#D3D3D3)
#   4. Material/texture descriptions (makes it tangible)
#   5. Concise but powerful (3-4 quality keywords max)

BASE_SUFFIX = (
    "isolated on solid light grey background, "
    "professional studio product photography, "
    "shot on Canon EOS R5 with 100mm macro lens, "
    "8k ultra high definition, photorealistic, "
    "razor sharp focus, studio strobe lighting with softbox, "
    "clean crisp edges, no shadows on background, centered composition"
)

# For offer logos / badges only (vector style)
VECTOR_SUFFIX = (
    "isolated on solid light grey background, "
    "clean vector graphic design, bold sharp typography, "
    "professional graphic design, high contrast, "
    "crisp clean edges, 8k resolution, print ready quality"
)

# ─────────────────────────────────────────────
# UNIVERSAL VARIATION BANKS (All Realistic)
# ─────────────────────────────────────────────

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
# 🍛 FOOD CATEGORIES
# ─────────────────────────────────────────────

INDIAN_FOOD = {
    "biryani": {
        "types": ["Hyderabadi dum biryani with leg piece", "Lucknowi awadhi biryani",
                  "Kolkata chicken biryani with potato", "Malabar biryani with coconut",
                  "Dindigul thalappakatti biryani", "Ambur star biryani",
                  "Thalassery biryani with cashews", "Sindhi biryani spicy",
                  "Kashmiri biryani with dry fruits", "Chettinad biryani pepper"],
        "vessels": ["deep ceramic bowl", "traditional copper handi pot",
                    "fresh banana leaf plate", "round steel plate thali",
                    "rustic clay pot", "engraved silver thali",
                    "handmade terracotta bowl", "heavy cast iron pot"],
        "garnish": ["topped with fresh mint leaves and fried onions",
                    "garnished with saffron strands and cashews",
                    "with boiled egg half and lemon wedge",
                    "with raita bowl and pickle on side",
                    "with crispy fried shallots and coriander"],
        "style": ["fine dining restaurant plating", "authentic home style serving",
                  "bustling street food style", "grand wedding feast presentation",
                  "royal Nawabi presentation"]
    },
    "dosa": {
        "types": ["golden crispy masala dosa with potato filling",
                  "paper thin ghee roast dosa", "fluffy set dosa stack",
                  "green pesarattu dosa", "lacy rava dosa with onions",
                  "delicate neer dosa translucent", "spicy egg dosa",
                  "cheese burst dosa", "butter ghee roast dosa crispy",
                  "stuffed paneer dosa golden brown"],
        "vessels": ["round stainless steel plate", "fresh green banana leaf",
                    "white ceramic dinner plate", "rustic wooden serving board",
                    "seasoned cast iron tawa"],
        "garnish": ["with white coconut chutney and sambar bowl",
                    "with red tomato chutney and green chutney",
                    "with melting butter pat on top",
                    "with gunpowder podi and sesame oil"],
        "style": ["South Indian breakfast style", "restaurant tiffin style",
                  "street food cart style", "traditional temple food style"]
    },
    "curry": {
        "types": ["rich creamy butter chicken", "vibrant green palak paneer",
                  "thick dark dal makhani", "spicy chole masala with whole chickpeas",
                  "Kerala fish curry in coconut gravy", "tender mutton rogan josh",
                  "prawn masala in red gravy", "rajma kidney bean curry",
                  "matar paneer with green peas", "smoky kadai chicken",
                  "fiery Chettinad chicken curry", "tangy Goan fish curry"],
        "vessels": ["glazed ceramic bowl", "hammered copper serving bowl",
                    "rustic clay pot", "deep stainless steel bowl",
                    "carved wooden bowl", "white porcelain bowl"],
        "garnish": ["with fresh coriander leaves on top", "with cream swirl drizzle",
                    "served with hot naan bread on side", "with steaming jeera rice",
                    "with lime pickle and papadum on side"],
        "style": ["restaurant fine dining plating", "home kitchen style",
                  "traditional thali style serving"]
    },
    "sweets": {
        "types": ["syrup soaked gulab jamun", "soft white rasgulla",
                  "crispy orange jalebi", "round besan ladoo",
                  "silver topped kaju barfi", "creamy rice kheer",
                  "rich gajar ka halwa", "melt in mouth peda",
                  "ghee dripping mysore pak", "motichoor ladoo textured",
                  "diamond cut kaju katli", "aromatic rava kesari"],
        "vessels": ["polished silver plate", "traditional brass plate",
                    "white ceramic dessert plate", "small clay cup kulhad",
                    "decorative mithai box", "fresh banana leaf"],
        "garnish": ["with edible silver vark on top", "with chopped pistachio garnish",
                    "with dried rose petals", "with saffron strands",
                    "with assorted dry fruit topping"],
        "style": ["festive celebration presentation", "sweet shop display style",
                  "homemade rustic style"]
    },
    "snacks": {
        "types": ["crispy golden samosa", "crunchy medu vada",
                  "spicy pani puri golgappa", "stuffed aloo tikki",
                  "hot onion bhaji pakora", "flaky kachori",
                  "tangy bhel puri", "crispy murukku", "masala vada",
                  "bread pakora stuffed", "dahi vada with curd"],
        "vessels": ["newspaper cone", "steel plate", "ceramic bowl",
                    "banana leaf", "paper plate", "wire basket"],
        "garnish": ["with green mint chutney", "with tamarind chutney drizzle",
                    "with sliced onion rings and lemon",
                    "with sev and coriander topping"],
        "style": ["street food style", "restaurant appetizer style",
                  "tea time snack style"]
    },
    "bread": {
        "types": ["puffed hot tandoori naan", "layered flaky parotta",
                  "whole wheat chapati", "crispy golden puri",
                  "stuffed aloo paratha", "thick roomali roti",
                  "garlic butter naan", "missi roti speckled",
                  "kulcha amritsari stuffed", "bhatura puffed"],
        "vessels": ["wicker basket lined with cloth", "steel plate",
                    "wooden board", "banana leaf", "tandoor edge"],
        "garnish": ["with butter melting on top", "with coriander sprinkle",
                    "with pickle and curd on side"],
        "style": ["tandoor fresh style", "home kitchen style", "dhaba style"]
    }
}

WORLD_FOOD = {
    "pizza": ["thin crust Margherita pizza with fresh basil",
              "deep dish pepperoni pizza with melted cheese pull",
              "authentic Neapolitan pizza with charred crust",
              "loaded BBQ chicken pizza", "four cheese pizza melted",
              "veggie supreme pizza with bell peppers",
              "truffle mushroom pizza gourmet", "prosciutto arugula pizza"],
    "burger": ["juicy beef cheeseburger with melting cheddar",
               "crispy fried chicken burger with coleslaw",
               "mushroom Swiss burger with grilled patty",
               "smoky BBQ bacon burger double stack",
               "black bean veggie burger with avocado",
               "smash burger with caramelized onions",
               "fish burger with tartar sauce and lettuce",
               "Korean bulgogi burger with kimchi"],
    "sushi": ["fresh salmon nigiri sushi glistening",
              "California roll with avocado and crab",
              "dragon roll sushi with eel topping",
              "ruby red tuna sashimi sliced",
              "colorful maki sushi platter assorted",
              "rainbow roll with mixed fish",
              "temaki hand roll cone shaped",
              "chirashi bowl with assorted sashimi"],
    "pasta": ["creamy spaghetti carbonara with egg yolk",
              "rich fettuccine alfredo with parmesan",
              "spicy penne arrabbiata with chili flakes",
              "layered lasagna bolognese cross section",
              "seafood linguine with clams and mussels",
              "basil pesto gnocchi with pine nuts",
              "creamy mushroom risotto with truffle",
              "handmade ravioli with sage brown butter"],
    "desserts": ["molten chocolate lava cake oozing",
                 "creamy strawberry cheesecake slice",
                 "classic tiramisu with cocoa dusting",
                 "caramelized creme brulee with torched top",
                 "colorful French macaron stack",
                 "golden Belgian waffle with berries and cream",
                 "tall ice cream sundae with toppings",
                 "velvety chocolate mousse in glass"],
    "chinese": ["steaming dim sum bamboo basket",
                "orange chicken with sesame seeds",
                "fried rice wok style with vegetables",
                "crispy spring rolls golden brown",
                "mapo tofu in spicy sauce",
                "Peking duck sliced with pancakes"],
    "mexican": ["loaded beef tacos with salsa",
                "chicken burrito bowl with guacamole",
                "nachos with melted cheese and jalapenos",
                "fresh ceviche in lime juice",
                "enchiladas with red sauce and sour cream",
                "churros with chocolate dipping sauce"]
}

# ─────────────────────────────────────────────
# 🍎 FRUITS & VEGETABLES (NEW)
# ─────────────────────────────────────────────

FRUITS = {
    "tropical": ["ripe golden mango whole and sliced", "fresh pineapple with crown",
                 "split open coconut with water", "ripe papaya half with seeds",
                 "bunch of yellow bananas", "cut open passion fruit",
                 "dragon fruit halved pink flesh", "rambutan cluster red hairy",
                 "jackfruit whole and opened", "guava cut green pink"],
    "berries": ["fresh red strawberries in heap", "plump blueberries cluster",
                "ripe raspberries pile", "blackberries glistening",
                "gooseberries green", "mixed berry assortment"],
    "citrus": ["orange sliced cross section juicy", "lemon whole and halved",
               "lime green fresh", "grapefruit pink halved",
               "tangerine peeled segments", "sweet lime mosambi"],
    "common": ["red apple shiny with water droplets", "green pear ripe",
               "purple grapes bunch on vine", "watermelon slice triangular",
               "pomegranate cut open red seeds", "peach fuzzy skin",
               "plum dark purple", "kiwi halved green flesh",
               "fig cut open revealing inside", "cherries pair with stem"]
}

VEGETABLES = {
    "leafy": ["fresh spinach bunch", "green lettuce head crisp",
              "kale leaves dark green curly", "cabbage head purple",
              "bok choy fresh", "curry leaves branch"],
    "root": ["fresh carrots bunch with tops", "red beetroot whole and sliced",
             "ginger root knobby", "turmeric root fresh yellow",
             "radish red round", "sweet potato orange flesh",
             "potato russet brown", "onion red halved rings visible"],
    "cooking": ["red tomato vine ripe", "green bell pepper glossy",
                "red chili peppers bunch", "eggplant brinjal purple glossy",
                "okra ladyfinger green", "bitter gourd textured",
                "drumstick moringa long", "green beans french fresh",
                "cauliflower head white", "broccoli head green florets"],
    "exotic": ["artichoke whole", "asparagus bunch green",
               "avocado halved with pit", "zucchini green",
               "mushroom variety assorted", "corn on cob yellow kernels"]
}

# ─────────────────────────────────────────────
# 🌸 FLOWERS
# ─────────────────────────────────────────────

FLOWERS = {
    "rose": ["deep red velvet rose", "soft pink garden rose", "pure white rose",
             "bright yellow rose", "sunset orange rose", "royal purple rose",
             "peach blush rose", "dark burgundy rose",
             "bicolor red and white rose", "coral pink rose"],
    "lotus": ["pink lotus flower in bloom", "pure white lotus open",
              "purple lotus with golden center", "red lotus bud opening",
              "lotus flower with green lily pad"],
    "jasmine": ["white jasmine flower cluster", "arabian jasmine buds",
                "star jasmine open petals", "jasmine garland string fresh",
                "jasmine buds and blooms mixed"],
    "sunflower": ["large yellow sunflower head with seeds visible",
                  "dwarf sunflower compact", "chocolate center sunflower",
                  "sunflower bouquet three stems", "sunflower fully open face"],
    "orchid": ["purple phalaenopsis orchid spray", "white dendrobium orchid stem",
               "pink cymbidium orchid bloom", "yellow oncidium orchid cluster",
               "spotted orchid exotic pattern", "red cattleya orchid large"],
    "marigold": ["deep orange marigold full bloom", "bright yellow marigold round",
                 "marigold garland thick fresh", "marigold bunch tied",
                 "large African marigold pompom"],
    "lily": ["elegant white calla lily", "spotted orange tiger lily",
             "fragrant pink stargazer lily", "yellow Asiatic lily",
             "purple water lily floating", "white Easter lily trumpet"],
    "hibiscus": ["bright red hibiscus with yellow stamen", "yellow hibiscus tropical",
                 "pink double hibiscus", "white hibiscus delicate",
                 "coral hibiscus bloom"],
    "other_flowers": ["cherry blossom branch pink", "lavender stems bunch purple",
                      "dahlia flower multi-layered petals", "lush peony bloom soft pink",
                      "tulip flower red single", "purple iris flower",
                      "gerbera daisy bright orange", "red anthurium heart shaped",
                      "bird of paradise orange and blue"]
}

FLOWER_STAGES = ["in full bloom petals open", "half open bud unfurling",
                 "just beginning to bloom", "tight fresh bud"]
FLOWER_CONTEXT = ["single long stem", "small arranged bouquet",
                  "with morning dewdrops on petals", "with fresh green leaves attached",
                  "freshly cut with water droplets"]

# ─────────────────────────────────────────────
# 🚗 VEHICLES
# ─────────────────────────────────────────────

CARS = {
    "sports_car": ["red Ferrari 458 Italia", "yellow Lamborghini Huracan",
                   "blue Porsche 911 GT3", "silver McLaren 720S",
                   "black Bugatti Chiron", "white Aston Martin DB11",
                   "orange McLaren 570S", "green Lotus Evora GT"],
    "suv": ["black Range Rover Sport", "white Toyota Land Cruiser",
            "silver BMW X5 M Sport", "blue Ford Endeavour",
            "grey Mercedes GLE AMG", "red Jeep Wrangler Rubicon",
            "white Hyundai Creta 2024", "black Kia Seltos GTX"],
    "sedan": ["white Toyota Camry hybrid", "silver Honda Accord",
              "blue BMW 3 Series M Sport", "black Mercedes C-Class AMG",
              "red Hyundai Verna turbo", "grey Maruti Ciaz"],
    "vintage": ["cherry red 1967 Ford Mustang GT", "baby blue 1957 Chevrolet Bel Air",
                "black 1937 Rolls Royce Phantom", "mint green 1963 Volkswagen Beetle",
                "white 1972 BMW E9 CSL", "yellow 1969 Chevrolet Camaro SS"],
    "electric": ["white Tesla Model S Plaid", "blue Rivian R1T pickup",
                 "silver Lucid Air Grand Touring", "red Chevrolet Bolt EV",
                 "black BMW iX xDrive", "white Hyundai Ioniq 6"],
    "luxury": ["black Rolls Royce Ghost", "silver Mercedes S-Class Maybach",
               "dark blue Bentley Continental GT", "white Lexus LS 500",
               "burgundy Maserati Quattroporte", "grey Audi A8 L"]
}

BIKES = {
    "sports_bike": ["red Honda CBR1000RR-R Fireblade", "blue Yamaha YZF-R1M",
                    "black Kawasaki Ninja ZX-10R", "orange KTM RC 390",
                    "yellow Suzuki GSX-R1000", "white BMW S1000RR M Sport",
                    "green Kawasaki Ninja H2", "red Ducati Panigale V4"],
    "cruiser": ["black Royal Enfield Classic 350 chrome",
                "orange Royal Enfield Meteor 350",
                "chrome Harley Davidson Fat Boy",
                "black Indian Chief Vintage",
                "burgundy Royal Enfield Super Meteor 650"],
    "adventure": ["orange KTM 390 Adventure", "blue Royal Enfield Himalayan 450",
                  "silver BMW R 1250 GS Adventure", "black Honda Africa Twin",
                  "yellow Yamaha Tenere 700 Rally"],
    "scooter": ["white Honda Activa 6G", "blue TVS Jupiter 125",
                "red Vespa Primavera 150", "black Suzuki Burgman Street",
                "yellow Yamaha Fascino 125"],
    "bicycle": ["carbon fiber road racing bicycle", "full suspension mountain bike",
                "chrome BMX freestyle bicycle", "city cruiser bicycle with basket",
                "orange gravel adventure bicycle", "compact folding bicycle"]
}

CAR_ANGLES = ["front 3/4 view showing grille and headlights",
              "side profile view full length", "rear 3/4 view showing tail lights",
              "dramatic front view symmetrical", "top aerial bird eye view",
              "dynamic low angle hero shot"]

# ─────────────────────────────────────────────
# 🌳 TREES & NATURE
# ─────────────────────────────────────────────

TREES = {
    "fruit_trees": ["mango tree with ripe hanging fruits", "tall coconut palm with coconuts",
                    "banana tree with fruit bunch", "papaya tree with green and ripe fruits",
                    "guava tree with ready fruits", "lemon tree with yellow lemons",
                    "orange tree with bright oranges", "apple tree heavy with red apples",
                    "fig tree with broad leaves", "pomegranate tree with split red fruits"],
    "tropical": ["tall coconut palm against sky", "slender areca palm",
                 "majestic traveller palm fan shaped", "banana plant cluster tropical",
                 "thick bamboo grove tall", "ancient Indian banyan tree with aerial roots",
                 "sacred peepal tree large"],
    "ornamental": ["cherry blossom tree in full pink bloom",
                   "jacaranda tree covered in purple flowers",
                   "golden shower tree dripping yellow blooms",
                   "flame of the forest red flowers",
                   "magnolia tree with large white blooms",
                   "weeping willow tree cascading branches"],
    "forest": ["tall pine tree coniferous", "giant spreading oak tree",
               "maple tree with autumn red leaves", "white bark birch tree",
               "tall cedar tree dark green", "silver bark eucalyptus tree",
               "massive redwood tree ancient", "dense bamboo grove"],
    "small_plants": ["echeveria succulent rosette", "barrel cactus with spines",
                     "aloe vera plant thick leaves", "golden money plant pothos",
                     "tall snake plant sansevieria", "Boston fern hanging",
                     "miniature bonsai tree aged", "tillandsia air plant",
                     "peace lily with white spathe", "rubber plant ficus glossy leaves"]
}

TREE_CONTEXT = ["full tree view showing roots to canopy", "bark and trunk detail close-up",
                "leaf texture macro detail", "with visible fruits or flowers",
                "in seasonal bloom state", "lush green healthy canopy"]

# ─────────────────────────────────────────────
# 🏺 POTS & VESSELS
# ─────────────────────────────────────────────

POTS_VESSELS = {
    "clay_pots": ["traditional red clay pot with texture", "terracotta water pot tall",
                  "hand painted blue clay pot", "black clay cooking pot rustic",
                  "glazed brown ceramic pot", "unglazed rustic clay vessel"],
    "metal_vessels": ["hammered shiny copper pot", "engraved brass lota round",
                      "polished steel cooking vessel", "ornate silver milk pot",
                      "antique patina bronze vessel", "seasoned iron kadai deep wok",
                      "dented aluminum pressure cooker used"],
    "decorative": ["blue and white Chinese porcelain vase",
                   "hand painted floral ceramic pot",
                   "ornate golden decorative urn",
                   "carved wooden bowl with grain visible",
                   "cut crystal glass vase sparkling",
                   "white marble decorative pot veined"],
    "cooking": ["flat clay tawa griddle seasoned", "heavy stone mortar and pestle granite",
                "woven wicker basket", "stacked bamboo steamer",
                "polished copper serving bowl", "brass measuring cups set nested"]
}

# ─────────────────────────────────────────────
# 💨 SMOKE & EFFECTS PNG
# ─────────────────────────────────────────────

SMOKE_EFFECTS = {
    "smoke": ["wispy white smoke trail thin", "thick billowing smoke column grey",
              "elegant curling smoke tendrils", "perfect smoke ring formation",
              "dense theatrical fog bank", "misty water vapor cloud soft"],
    "colored_smoke": ["vibrant red smoke bomb cloud", "electric blue smoke burst",
                      "neon green smoke plume", "royal purple smoke billow",
                      "bright yellow smoke trail", "deep orange smoke explosion"],
    "fire": ["realistic orange flame tongues", "intense blue gas flame",
             "crackling campfire with embers", "single candle flame warm glow",
             "bright fire sparks burst scattering", "fire trail motion streaked"],
    "sparkle": ["golden sparkle particle burst", "silver glitter explosion scattered",
                "magical dust particles floating", "warm fairy light particles",
                "star shaped sparkle burst bright", "colorful confetti burst celebration"]
}

# ─────────────────────────────────────────────
# ☀️ SKY ELEMENTS & CELESTIAL (ALL REALISTIC)
# ─────────────────────────────────────────────

SKY_ELEMENTS = {
    "sun": ["bright radiant sun with light rays", "golden sunrise sun glowing",
            "warm setting sun orange red", "sun with dramatic god rays",
            "partial solar eclipse sun", "sun through clouds rays breaking"],
    "moon": ["full moon realistic cratered surface", "thin crescent moon glowing",
             "half moon phase detailed", "golden supermoon glowing large",
             "moon with surrounding stars", "blood moon lunar eclipse red"],
    "stars": ["bright gold five pointed star metallic", "shooting star with trail streak",
              "star cluster like constellation pattern", "glowing bright star burst",
              "north star with light rays", "metallic 3D gold star shiny"],
    "clouds": ["fluffy white cumulus cloud", "dark grey storm cumulonimbus cloud",
               "rain cloud with visible rain streaks", "cotton ball like white cloud",
               "rainbow arching over white cloud", "golden cloud lit by sunrise"],
    "weather": ["forked lightning bolt bright", "double rainbow arc vivid colors",
                "detailed ice snowflake crystal macro", "rain drops mid air frozen",
                "tornado funnel cloud dramatic", "wind swirl with leaves debris"]
}

# ─────────────────────────────────────────────
# 🖼️ FRAMES & BORDERS
# ─────────────────────────────────────────────

FRAMES_BORDERS = {
    "wedding": ["ornate carved gold wedding frame", "floral wedding border with pink roses",
                "elegant pearl white wedding frame", "vintage gold filigree flourish frame",
                "romantic flower arch wedding frame"],
    "festival": ["Diwali diya oil lamp border gold", "Christmas holly berry border green red",
                 "Eid crescent moon star frame gold", "Pongal kolam rangoli border",
                 "New Year fireworks celebration frame", "Holi colorful powder splash border"],
    "modern": ["minimalist thin gold line border", "geometric hexagonal pattern frame",
               "neon glow edge rectangular border", "rounded corner clean modern frame",
               "artistic brushstroke edge border", "watercolor edge splash frame"],
    "nature": ["circular floral wreath frame", "tropical palm leaves corner border",
               "bamboo wooden rustic frame", "vine and wildflower winding border",
               "sunflower circle frame", "autumn maple leaves corner border"]
}

# ─────────────────────────────────────────────
# 🏷️ OFFER LOGOS & BADGES (VECTOR STYLE KEPT)
# ─────────────────────────────────────────────

OFFER_LOGOS = {
    "discount": ["50% OFF sale badge", "30% discount sticker circular",
                 "20% OFF rounded badge", "FLAT 40% OFF rectangular label",
                 "MEGA SALE starburst badge", "CLEARANCE SALE hanging tag",
                 "10% OFF coupon style stamp", "SAVE 25% ribbon label"],
    "buy_deals": ["BUY 1 GET 1 FREE badge", "BUY 2 GET 1 FREE sticker",
                  "FREE GIFT with purchase badge", "COMBO OFFER deal seal"],
    "special_offers": ["SPECIAL OFFER starburst shape", "LIMITED TIME OFFER badge urgent",
                       "TODAY ONLY deal badge", "FLASH SALE lightning bolt badge",
                       "BEST PRICE guarantee badge green", "HOT DEAL fire theme badge",
                       "EXCLUSIVE OFFER gold seal", "VIP OFFER crown premium badge"],
    "seasonal": ["DIWALI SPECIAL festive offer badge", "SUMMER SALE sunny badge",
                 "FESTIVAL OFFER celebration label", "NEW YEAR DEAL confetti badge",
                 "EID MUBARAK special offer", "CHRISTMAS SALE red green sticker"],
    "quality": ["BEST SELLER gold badge award", "TOP RATED five star badge",
                "NEW ARRIVAL ribbon label", "TRENDING NOW fire badge",
                "PREMIUM QUALITY shield seal", "100% GENUINE stamp badge"]
}

# ─────────────────────────────────────────────
# 🏠 FURNITURE & HOME
# ─────────────────────────────────────────────

FURNITURE = {
    "seating": ["modern minimalist white armchair", "classic wooden rocking chair",
                "deep blue velvet tufted sofa", "executive leather office chair",
                "natural rattan peacock chair", "antique carved wooden bench",
                "mid century modern accent chair", "bean bag chair leather"],
    "tables": ["tempered glass top coffee table", "solid wood farmhouse dining table",
               "Italian marble top side table", "compact folding utility table",
               "antique hand carved wooden table", "industrial metal and wood desk"],
    "storage": ["tall oak bookshelf with books", "modern white sliding door wardrobe",
                "vintage wooden chest of drawers", "handwoven rattan storage basket",
                "wall mounted floating wooden shelves", "metal locker industrial style"],
    "beds": ["king size wooden platform bed frame", "children wooden bunk bed",
             "luxury upholstered tufted headboard bed", "minimalist black metal daybed",
             "four poster canopy bed wooden", "storage bed with drawers"]
}

# ─────────────────────────────────────────────
# 🔧 TOOLS & EQUIPMENT
# ─────────────────────────────────────────────

TOOLS = {
    "hand_tools": ["steel claw hammer wooden handle", "chrome adjustable wrench",
                   "professional screwdriver set in case", "combination pliers red handle",
                   "retractable steel measuring tape", "hardened steel hacksaw",
                   "wood chisel set with wooden handles", "manual hand drill vintage"],
    "kitchen_tools": ["Damascus steel chef knife set in block",
                      "olive wood spatula and spoon set",
                      "Lodge cast iron skillet seasoned",
                      "stainless steel mixing bowl set nested",
                      "marble rolling pin with steel handles",
                      "box grater four sided stainless",
                      "deep ladle stainless long handle",
                      "spring loaded kitchen tongs steel"],
    "garden_tools": ["steel garden spade with ash handle", "bypass pruning shears sharp",
                     "galvanized green watering can", "four tine garden fork steel",
                     "hand trowel with ergonomic grip"],
    "power_tools": ["cordless DeWalt electric drill", "Bosch angle grinder sparking",
                    "variable speed jigsaw power tool", "Makita circular saw",
                    "random orbital sander", "impact driver cordless"]
}

# ─────────────────────────────────────────────
# 🎉 FESTIVAL & EVENTS
# ─────────────────────────────────────────────

FESTIVALS = {
    "diwali": ["brass diya oil lamp with flame glowing", "colorful rangoli floor pattern with flowers",
               "fireworks burst in night sky colorful", "golden Lakshmi idol detailed",
               "decorated Diwali gift box with ribbon", "lit sparkler trail of light"],
    "christmas": ["decorated Christmas pine tree with ornaments", "realistic Santa Claus figurine detailed",
                  "fresh Christmas wreath with holly berries", "wrapped Christmas gift box red ribbon gold",
                  "snowman figurine with scarf and hat", "gold star Christmas tree topper"],
    "pongal": ["overflowing pongal pot with rice traditional", "fresh sugarcane stalk long",
               "white rice flour kolam floor art", "sweet pongal in clay pot",
               "decorative sun symbol brass pongal"],
    "eid": ["golden crescent moon and star ornament", "ornate Eid lantern fanoos lit",
            "fresh dates fruit on silver plate", "intricate henna mehndi on hand realistic",
            "mosque dome silhouette detailed", "wrapped Eid gift box elegant"],
    "general": ["birthday cake with lit candles frosted", "helium balloon bunch colorful shiny",
                "exploding party popper with confetti", "black graduation cap with tassel",
                "gold trophy cup engraved", "gift box wrapped with satin ribbon bow"]
}

# ─────────────────────────────────────────────
# 🦋 BIRDS & INSECTS
# ─────────────────────────────────────────────

BIRDS_INSECTS = {
    "birds": ["male peacock with full tail feathers displayed",
              "colorful macaw parrot on branch",
              "kingfisher bird vivid blue and orange",
              "pink flamingo standing one leg",
              "toucan with large colorful beak",
              "bald eagle in flight wings spread",
              "barn owl perched with intense eyes",
              "ruby throated hummingbird hovering at flower",
              "European robin red breast on branch",
              "white dove pigeon in flight"],
    "butterflies": ["monarch butterfly orange and black wings open",
                    "blue morpho butterfly iridescent wings",
                    "swallowtail butterfly yellow and black",
                    "cabbage white butterfly on flower",
                    "painted lady butterfly detailed wings",
                    "glasswing butterfly transparent wings"],
    "insects": ["ladybug seven spots on green leaf",
                "honeybee collecting pollen on flower",
                "dragonfly iridescent wings resting on reed",
                "praying mantis green on branch hunting pose",
                "stag beetle large mandibles shiny",
                "firefly glowing abdomen at dusk"]
}

# ─────────────────────────────────────────────
# 💎 JEWELLERY
# ─────────────────────────────────────────────

JEWELLERY = {
    "necklace": ["heavy gold temple necklace with ruby pendant",
                 "diamond solitaire pendant on thin chain",
                 "classic pearl strand necklace lustrous",
                 "ruby and gold traditional necklace",
                 "emerald pendant on gold chain",
                 "bridal kundan necklace set elaborate",
                 "oxidized silver tribal necklace",
                 "beaded colorful statement necklace"],
    "earrings": ["gold jhumka bell earrings with pearls",
                 "round diamond stud earrings sparkling",
                 "pearl drop earrings on gold hooks",
                 "chandbali gold earrings crescent shaped",
                 "large gold hoop earrings polished",
                 "crystal chandelier earrings dangling"],
    "rings": ["diamond solitaire engagement ring platinum",
              "plain gold band ring polished",
              "oval ruby ring in gold setting",
              "emerald cut ring with diamonds",
              "oxidized silver cocktail ring large",
              "matching wedding ring set diamond band"],
    "bangles": ["set of gold bangles stacked",
                "colorful glass bangles Indian traditional",
                "thick silver bangle bracelet engraved",
                "bridal kundan bangle set ornate",
                "heavy gold kada bangle single"]
}

# ─────────────────────────────────────────────
# 🐄 ANIMALS
# ─────────────────────────────────────────────

ANIMALS = {
    "farm": ["Indian white cow with hump standing",
             "water buffalo black with curved horns",
             "brown and white goat with beard",
             "fluffy white sheep woolly coat",
             "brown country hen standing alert",
             "white Pekin duck wadding"],
    "wild": ["African elephant bull with tusks",
             "male lion with full golden mane",
             "Bengal tiger orange with black stripes",
             "African leopard spotted in alert pose",
             "tall giraffe with unique pattern",
             "zebra with bold black and white stripes",
             "Indian rhinoceros grey armored skin",
             "hippopotamus mouth partially open"],
    "sea": ["bottlenose dolphin jumping out of water",
            "blue whale massive body",
            "great white shark with open mouth",
            "red octopus with spread tentacles",
            "green sea turtle swimming",
            "orange clownfish in anemone",
            "orange starfish five arms",
            "translucent jellyfish with trailing tentacles"],
    "pets": ["golden retriever dog happy portrait",
             "white Persian cat fluffy sitting",
             "white fluffy rabbit sitting upright",
             "golden Syrian hamster cute",
             "Indian ringneck parakeet green perched",
             "betta fish with flowing colorful fins"]
}

# ─────────────────────────────────────────────
# 📱 ELECTRONICS & GADGETS (NEW)
# ─────────────────────────────────────────────

ELECTRONICS = {
    "phones": ["latest iPhone Pro with triple camera system",
               "Samsung Galaxy S Ultra flagship phone",
               "Google Pixel Pro phone clean design",
               "OnePlus flagship phone sleek black"],
    "laptops": ["MacBook Pro silver open showing screen",
                "gaming laptop with RGB keyboard glowing",
                "thin ultrabook laptop silver",
                "convertible 2-in-1 laptop tablet mode"],
    "audio": ["over-ear premium headphones leather cushion",
              "wireless earbuds in charging case open",
              "portable Bluetooth speaker cylindrical",
              "studio monitor headphones professional",
              "vintage turntable record player"],
    "cameras": ["DSLR camera with lens attached professional",
                "mirrorless camera compact body",
                "vintage film camera analog",
                "action camera GoPro style",
                "instant Polaroid camera retro"],
    "wearables": ["smartwatch with digital face display",
                  "fitness band tracker on display",
                  "smart glasses tech wearable"],
    "accessories": ["wireless charging pad circular",
                    "power bank portable charger",
                    "USB-C hub multiport adapter",
                    "mechanical gaming keyboard RGB",
                    "ergonomic wireless mouse"]
}

# ─────────────────────────────────────────────
# 🌶️ SPICES (NEW)
# ─────────────────────────────────────────────

SPICES = {
    "whole_spices": ["whole cinnamon sticks bundle", "green cardamom pods pile",
                     "star anise whole dried", "whole cloves dried pile",
                     "black peppercorns heap", "whole cumin seeds mound",
                     "mustard seeds yellow and black", "fenugreek seeds pile",
                     "dried red chili whole bunch", "bay leaves dried"],
    "ground_spices": ["bright turmeric powder mound", "red chili powder vibrant",
                      "coriander powder golden brown", "cumin powder aromatic",
                      "garam masala powder blend", "black pepper powder fresh ground"],
    "fresh_herbs": ["fresh coriander cilantro bunch", "fresh mint leaves bunch",
                    "curry leaves on stem fresh", "fresh basil bunch green",
                    "lemongrass stalks fresh", "fresh rosemary sprigs"]
}

SPICE_CONTEXT = ["in small brass bowl", "on wooden spoon", "scattered on slate surface",
                 "in glass jar open", "in traditional spice box compartment"]

# ─────────────────────────────────────────────
# 🥤 BEVERAGES & DRINKS (NEW)
# ─────────────────────────────────────────────

BEVERAGES = {
    "hot_drinks": ["steaming cup of masala chai in glass cup",
                   "latte art coffee in ceramic cup",
                   "black coffee in white mug with steam",
                   "green tea in glass cup clear",
                   "hot chocolate with whipped cream and cocoa",
                   "golden turmeric latte in mug"],
    "cold_drinks": ["iced coffee with cream layered in tall glass",
                    "fresh orange juice in glass with ice",
                    "green smoothie in mason jar",
                    "mango lassi in tall glass creamy",
                    "rose milk falooda with ice cream",
                    "fresh coconut water in tender coconut",
                    "lemonade with mint leaves in pitcher",
                    "buttermilk chaas in brass glass"],
    "cocktails_mocktails": ["blue lagoon mocktail layered",
                            "mojito with crushed ice and mint",
                            "virgin pina colada with pineapple wedge",
                            "fruit punch bowl colorful",
                            "sparkling water with lemon slice"],
    "traditional": ["filter coffee in brass davara tumbler set",
                    "masala chai in terracotta kulhad cup",
                    "jigarthanda cold drink in tall glass",
                    "thandai with almond and saffron",
                    "paneer soda pink in glass bottle"]
}

# ─────────────────────────────────────────────
# 👟 SHOES & FOOTWEAR (NEW)
# ─────────────────────────────────────────────

SHOES = {
    "sneakers": ["white Nike Air Force 1 sneakers", "Adidas Ultraboost running shoes black",
                 "New Balance 550 retro sneakers", "Converse Chuck Taylor high top red",
                 "Puma RS-X colorful sneakers", "minimalist white leather sneakers clean"],
    "formal": ["black Oxford leather shoes polished", "brown Derby brogue shoes",
               "patent leather dress shoes shiny", "suede loafers tan",
               "monk strap shoes burgundy leather"],
    "traditional": ["brown leather kolhapuri chappal", "embroidered Rajasthani jutti colorful",
                    "Kolkata leather sandal classic", "wooden paduka traditional"],
    "boots": ["brown Chelsea boots leather", "black combat military boots",
              "tan suede desert boots", "hiking boots waterproof rugged",
              "cowboy boots embroidered leather"],
    "sandals": ["leather gladiator sandals brown", "rubber flip flops colorful",
                "sports sandals with velcro straps", "wooden clog sandals"]
}

# ─────────────────────────────────────────────
# 👜 BAGS & LUGGAGE (NEW)
# ─────────────────────────────────────────────

BAGS = {
    "handbags": ["luxury leather tote bag tan", "quilted designer crossbody bag black",
                 "structured satchel bag burgundy leather", "mini bucket bag red",
                 "woven straw beach bag natural"],
    "backpacks": ["hiking backpack with gear loops green",
                  "leather backpack vintage brown",
                  "modern laptop backpack grey slim",
                  "canvas school backpack navy",
                  "roll-top urban backpack black"],
    "travel": ["hard shell suitcase large silver", "leather duffle bag brown",
               "cabin trolley bag compact black", "vintage trunk suitcase",
               "travel organizer pouch set"],
    "traditional": ["jute shopping bag printed", "cotton tote bag embroidered",
                    "brass clutch purse ornate", "silk potli bag drawstring"]
}

# ─────────────────────────────────────────────
# 💄 COSMETICS & BEAUTY (NEW)
# ─────────────────────────────────────────────

COSMETICS = {
    "makeup": ["red lipstick bullet open luxury gold case",
               "eyeshadow palette with mirror open",
               "mascara wand with product",
               "foundation bottle glass with pump",
               "compact powder with mirror and puff",
               "makeup brush set in holder"],
    "skincare": ["glass serum bottle with dropper",
                 "moisturizer cream jar open white",
                 "face wash tube squeezed",
                 "sunscreen bottle SPF label",
                 "sheet mask packet with mask"],
    "fragrance": ["luxury perfume bottle with gold cap",
                  "cologne bottle masculine design",
                  "attar perfume oil bottle traditional",
                  "reed diffuser with sticks in glass bottle"],
    "hair_care": ["shampoo bottle professional salon",
                  "wooden hair brush boar bristle",
                  "hair oil bottle with herbs visible",
                  "hair dryer professional black and gold"]
}

# ─────────────────────────────────────────────
# 🏏 SPORTS EQUIPMENT (NEW)
# ─────────────────────────────────────────────

SPORTS = {
    "cricket": ["cricket bat willow wood with grip",
                "red cricket ball leather with seam",
                "cricket helmet with face guard",
                "cricket wicket stumps and bails set",
                "cricket batting gloves pair white"],
    "football": ["FIFA match football with panels",
                 "football boots with studs",
                 "goalkeeper gloves professional",
                 "football shin guards pair"],
    "badminton_tennis": ["badminton racket with shuttlecock",
                         "tennis racket with green ball",
                         "table tennis paddle with ball",
                         "badminton shuttlecock feather white"],
    "fitness": ["pair of steel dumbbells heavy",
                "yoga mat rolled purple",
                "resistance bands set colored",
                "kettlebell cast iron black",
                "skipping rope with counter"],
    "other_sports": ["basketball orange textured",
                     "hockey stick and puck",
                     "golf club driver and ball on tee",
                     "boxing gloves red leather laced",
                     "swimming goggles with strap",
                     "archery bow and arrow set"]
}

# ─────────────────────────────────────────────
# 🎵 MUSICAL INSTRUMENTS (NEW)
# ─────────────────────────────────────────────

MUSICAL_INSTRUMENTS = {
    "string": ["acoustic guitar wood grain visible",
               "electric guitar sunburst finish",
               "classical violin with bow",
               "Indian sitar with resonator",
               "Indian veena traditional ornate",
               "ukulele small four string",
               "cello full size wooden"],
    "percussion": ["tabla pair Indian drums",
                   "mridangam South Indian drum",
                   "djembe African hand drum",
                   "drum kit full set professional",
                   "tambourine with jingles",
                   "Indian dholak double headed"],
    "wind": ["bamboo flute Indian bansuri",
             "saxophone golden brass",
             "trumpet polished brass",
             "clarinet black wooden",
             "shehnai Indian wedding instrument",
             "harmonica silver chrome"],
    "keyboard": ["grand piano black glossy",
                 "harmonium Indian keyboard bellows",
                 "electronic keyboard synthesizer",
                 "accordion red with bellows"]
}

# ─────────────────────────────────────────────
# 🪔 RELIGIOUS & POOJA ITEMS (NEW)
# ─────────────────────────────────────────────

POOJA_ITEMS = {
    "idols": ["brass Ganesha idol detailed", "marble Krishna playing flute idol",
              "bronze Nataraja Shiva dancing idol", "wooden Buddha meditating statue",
              "brass Lakshmi idol standing on lotus", "stone carved Hanuman idol",
              "panchaloha Saraswati idol with veena", "copper Murugan vel spear"],
    "pooja_vessels": ["brass pooja thali with items complete",
                      "copper kalash water pot with coconut",
                      "silver kumkum box small ornate",
                      "brass deepam oil lamp with wick",
                      "bronze bell with handle pooja",
                      "brass incense holder agarbatti stand",
                      "copper pancha patra and uddharani set",
                      "silver camphor plate aarti"],
    "garlands": ["fresh jasmine flower garland maalai long",
                 "rose petal garland red and pink",
                 "marigold and jasmine mixed garland thick",
                 "tulsi holy basil mala beads",
                 "rudraksha bead mala prayer"],
    "accessories": ["sandalwood paste on stone grinder",
                    "vibhuti holy ash in container",
                    "kumkum red powder in brass box",
                    "agarbathi incense sticks bundle",
                    "camphor tablets white on brass plate",
                    "coconut whole with turmeric and flowers"]
}

# ─────────────────────────────────────────────
# 👔 CLOTHING & TEXTILES (NEW)
# ─────────────────────────────────────────────

CLOTHING = {
    "indian_traditional": ["folded Kanchipuram silk saree gold border",
                           "Banarasi silk saree rich brocade",
                           "white Kerala kasavu mundu and veshti",
                           "colorful Rajasthani bandhani dupatta",
                           "embroidered Lucknowi chikankari kurta white",
                           "Mysore silk saree folded with pallu visible"],
    "mens_wear": ["crisp white formal dress shirt folded",
                  "navy blue blazer jacket on hanger",
                  "black leather belt coiled",
                  "silk necktie rolled assorted colors",
                  "denim jeans folded stack blue"],
    "accessories": ["silk scarf folded elegant", "woolen shawl Kashmiri embroidered",
                    "cotton handkerchief white folded", "leather wallet brown open",
                    "aviator sunglasses gold frame on surface"]
}

# ─────────────────────────────────────────────
# 🏥 MEDICAL & HEALTH (NEW)
# ─────────────────────────────────────────────

MEDICAL = {
    "equipment": ["stethoscope silver on surface",
                  "digital blood pressure monitor",
                  "clinical thermometer digital",
                  "pulse oximeter on finger display",
                  "first aid kit box red cross open"],
    "supplies": ["syringe with needle medical",
                 "medicine pill capsule assorted colors",
                 "bandage roll white cotton",
                 "face mask surgical blue disposable",
                 "medicine bottle amber with label"],
    "ayurveda": ["mortar and pestle with herbs ayurvedic",
                 "neem leaves and powder",
                 "tulsi holy basil leaves fresh",
                 "turmeric root and powder golden",
                 "ashwagandha root dried"]
}

# ─────────────────────────────────────────────
# ✏️ STATIONERY & OFFICE (NEW)
# ─────────────────────────────────────────────

STATIONERY = {
    "writing": ["fountain pen with gold nib", "mechanical pencil with lead",
                "set of colored pencils in row", "ballpoint pen set luxury",
                "calligraphy brush pen bamboo", "highlighter set fluorescent colors"],
    "desk": ["leather bound notebook closed", "spiral notebook open blank pages",
             "desk organizer wooden with supplies", "tape dispenser and scissors set",
             "stapler and staple remover set", "paper weight crystal globe"],
    "art_supplies": ["watercolor paint palette with brushes",
                     "acrylic paint tubes assorted colors",
                     "sketch pad with charcoal pencils",
                     "canvas on easel blank white",
                     "oil pastel set in box open"]
}

# ─────────────────────────────────────────────
# CLIPARTS (Realistic 3D style only)
# ─────────────────────────────────────────────

CLIPARTS = {
    "arrows": ["glossy 3D red arrow pointing right", "curved metallic blue arrow",
               "double headed chrome arrow", "circular loop arrow gold metallic",
               "3D gold arrow pointing upward", "green metallic arrow bold"],
    "hearts": ["glossy 3D red heart shape", "pink polished heart smooth",
               "metallic gold heart shape reflective", "cracked broken heart two pieces",
               "heart made of real red roses", "glass crystal heart transparent",
               "rainbow gradient heart 3D", "heart with golden angel wings"],
    "ribbons_banners": ["satin golden ribbon banner unfurled", "red silk victory ribbon",
                        "blue satin award ribbon rosette", "scroll parchment ribbon unfurled",
                        "silk banner flag flowing red", "gold medal with ribbon award"],
    "checkmarks_x": ["3D green checkmark glossy tick", "3D red X cross mark",
                     "metallic gold star rating five point", "3D thumbs up hand realistic",
                     "3D thumbs down hand realistic", "jeweled gold crown royal"],
    "symbols": ["metallic peace sign symbol", "infinity symbol chrome reflective",
                "yin yang symbol marble texture", "nautical anchor brass",
                "compass rose brass detailed", "four leaf clover green realistic",
                "fleur de lis gold ornate", "Celtic knot silver engraved"]
}


# ═════════════════════════════════════════════
# PROMPT GENERATOR CLASS V2
# ═════════════════════════════════════════════

class PromptEngine:
    def __init__(self):
        self.generated_prompts = set()
        self.prompt_list = []

    def make_prompt(self, subject, extra_details=""):
        """Create a FLUX-optimized prompt for ultra-realistic photography"""
        angle = random.choice(CAMERA_ANGLES)
        lighting = random.choice(LIGHTING_STYLES)
        quality = random.choice(DETAIL_QUALITY)
        photo_style = random.choice(PHOTO_STYLES)

        parts = [subject]
        if extra_details:
            parts.append(extra_details)
        parts.extend([angle, lighting, quality, photo_style, BASE_SUFFIX])

        return ", ".join(parts)

    # ─── FOOD ───────────────────────────────
    def generate_food_prompts(self):
        prompts = []
        photo_approaches = ["close-up food photography", "overhead flat lay food shot",
                            "angled hero shot food photography", "lifestyle food photography"]

        # Indian food
        for dish, data in INDIAN_FOOD.items():
            for type_ in data["types"]:
                for vessel in data["vessels"]:
                    for garnish in data["garnish"][:3]:
                        for style in data["style"]:
                            subject = f"{type_} served in {vessel}, {garnish}, {style}"
                            p = self.make_prompt(subject)
                            prompts.append({"category": "food/indian", "subcategory": dish,
                                            "prompt": p, "seed": random.randint(1, 999999)})

        # World food
        vessels_world = ["on rustic wooden board", "on white ceramic dinner plate",
                         "in deep ceramic bowl", "on dark slate serving board",
                         "in clear glass bowl", "on cast iron skillet hot",
                         "in handmade terracotta dish"]
        for dish, items in WORLD_FOOD.items():
            for item in items:
                for vessel in vessels_world:
                    for approach in photo_approaches:
                        p = self.make_prompt(item, f"{vessel}, {approach}")
                        prompts.append({"category": "food/world", "subcategory": dish,
                                        "prompt": p, "seed": random.randint(1, 999999)})
        return prompts

    # ─── FRUITS & VEGETABLES ─────────────────
    def generate_fruit_veg_prompts(self):
        prompts = []
        contexts = ["whole intact", "sliced cross section showing inside",
                    "arranged in group pile", "with water droplets fresh"]

        for fruit_type, fruits in FRUITS.items():
            for fruit in fruits:
                for context in contexts:
                    p = self.make_prompt(f"{fruit}, {context}")
                    prompts.append({"category": "fruits", "subcategory": fruit_type,
                                    "prompt": p, "seed": random.randint(1, 999999)})

        for veg_type, vegs in VEGETABLES.items():
            for veg in vegs:
                for context in contexts:
                    p = self.make_prompt(f"{veg}, {context}")
                    prompts.append({"category": "vegetables", "subcategory": veg_type,
                                    "prompt": p, "seed": random.randint(1, 999999)})
        return prompts

    # ─── FLOWERS (100% Realistic only) ──────
    def generate_flower_prompts(self):
        prompts = []
        # ALL styles are photography — NO watercolor, illustration, etc.
        realistic_approaches = [
            "macro lens close-up photography",
            "botanical studio photography",
            "fine art floral photography",
            "natural light floral photography"
        ]

        for flower_type, varieties in FLOWERS.items():
            for variety in varieties:
                for stage in FLOWER_STAGES:
                    for context in FLOWER_CONTEXT:
                        for approach in realistic_approaches:
                            subject = f"{variety} {stage}, {context}, {approach}"
                            p = self.make_prompt(subject)
                            prompts.append({"category": "flowers", "subcategory": flower_type,
                                            "prompt": p, "seed": random.randint(1, 999999)})
        return prompts

    # ─── VEHICLES ────────────────────────────
    def generate_vehicle_prompts(self):
        prompts = []
        car_details = ["pristine clean polished bodywork", "detailed chrome reflections",
                       "gleaming factory fresh paintwork", "visible interior through windows"]

        for car_type, models in CARS.items():
            for model in models:
                for angle in CAR_ANGLES:
                    for detail in car_details:
                        p = self.make_prompt(f"{model}, {angle}", detail)
                        prompts.append({"category": "vehicles/cars", "subcategory": car_type,
                                        "prompt": p, "seed": random.randint(1, 999999)})

        bike_details = ["chrome exhaust pipes gleaming", "detailed engine visible",
                        "shiny tank and bodywork", "rubber tire tread detail"]
        for bike_type, models in BIKES.items():
            for model in models:
                for angle in CAR_ANGLES:
                    for detail in bike_details:
                        p = self.make_prompt(f"{model}, {angle}", detail)
                        prompts.append({"category": "vehicles/bikes", "subcategory": bike_type,
                                        "prompt": p, "seed": random.randint(1, 999999)})
        return prompts

    # ─── TREES & NATURE ─────────────────────
    def generate_nature_prompts(self):
        prompts = []
        seasons = ["summer lush green foliage", "autumn golden orange leaves",
                   "spring fresh blossoms", "monsoon rain glistening wet",
                   "tropical humid lush"]

        for tree_type, trees in TREES.items():
            for tree in trees:
                for context in TREE_CONTEXT:
                    for season in seasons:
                        p = self.make_prompt(f"{tree}, {context}, {season}")
                        prompts.append({"category": "nature/trees", "subcategory": tree_type,
                                        "prompt": p, "seed": random.randint(1, 999999)})
        return prompts

    # ─── POTS & VESSELS ─────────────────────
    def generate_pots_prompts(self):
        prompts = []
        finishes = ["brand new clean", "aged patina surface", "antique weathered texture",
                    "polished shiny reflective", "hand painted floral motif",
                    "carved decorative pattern", "plain traditional finish"]
        sizes = ["small", "medium", "large"]

        for pot_type, pots in POTS_VESSELS.items():
            for pot in pots:
                for finish in finishes:
                    for size in sizes:
                        p = self.make_prompt(f"{size} {pot}, {finish}")
                        prompts.append({"category": "pots_vessels", "subcategory": pot_type,
                                        "prompt": p, "seed": random.randint(1, 999999)})
        return prompts

    # ─── SMOKE & EFFECTS ────────────────────
    def generate_smoke_prompts(self):
        prompts = []
        sizes = ["thin wispy", "medium thick", "dense heavy", "large billowing"]
        movements = ["rising upward", "swirling slowly", "dispersing outward",
                     "curling sideways", "drifting gently"]

        smoke_suffix = (
            "isolated on solid light grey background, "
            "high contrast, sharp edges, 8k resolution, "
            "real smoke photography, no background elements"
        )

        for effect_type, effects in SMOKE_EFFECTS.items():
            for effect in effects:
                for size in sizes:
                    for movement in movements:
                        p = f"{size} {effect}, {movement}, {smoke_suffix}"
                        prompts.append({"category": "effects", "subcategory": effect_type,
                                        "prompt": p, "seed": random.randint(1, 999999)})
        return prompts

    # ─── SKY & CELESTIAL (Realistic only) ───
    def generate_sky_prompts(self):
        prompts = []
        realistic_styles = ["photorealistic rendering", "high detail realistic",
                            "3D metallic finish", "glossy realistic surface"]
        color_moods = ["warm golden tones", "cool blue tones", "vivid bright colors"]

        for element_type, elements in SKY_ELEMENTS.items():
            for element in elements:
                for style in realistic_styles:
                    for mood in color_moods:
                        p = self.make_prompt(f"{element}, {style}, {mood}")
                        prompts.append({"category": "sky_celestial", "subcategory": element_type,
                                        "prompt": p, "seed": random.randint(1, 999999)})
        return prompts

    # ─── CLIPARTS (Realistic 3D only) ───────
    def generate_clipart_prompts(self):
        prompts = []
        realistic_styles = ["glossy 3D rendered", "polished metallic chrome",
                            "realistic material texture", "smooth photorealistic surface"]
        colors = ["red", "blue", "gold", "green", "silver"]

        for clip_type, clips in CLIPARTS.items():
            for clip in clips:
                for style in realistic_styles:
                    for color in colors[:3]:
                        p = self.make_prompt(f"{clip}, {color} tinted, {style}")
                        prompts.append({"category": "cliparts", "subcategory": clip_type,
                                        "prompt": p, "seed": random.randint(1, 999999)})
        return prompts

    # ─── FRAMES & BORDERS ───────────────────
    def generate_frame_prompts(self):
        prompts = []
        colors = ["gold", "silver", "rose gold", "antique bronze",
                  "platinum", "copper", "pearl white"]
        styles = ["ornate hand carved detailed", "minimal clean modern",
                  "vintage aged patina", "geometric art deco",
                  "floral intricate relief", "rustic reclaimed wood"]

        for frame_type, frames in FRAMES_BORDERS.items():
            for frame in frames:
                for color in colors:
                    for style in styles:
                        p = (f"{frame}, {color} color, {style} design, "
                             f"isolated on solid light grey background, "
                             f"photorealistic material texture, 8k high detail, "
                             f"professional product photography")
                        prompts.append({"category": "frames_borders", "subcategory": frame_type,
                                        "prompt": p, "seed": random.randint(1, 999999)})
        return prompts

    # ─── OFFER LOGOS (VECTOR STYLE) ─────────
    def generate_offer_logo_prompts(self):
        prompts = []
        color_schemes = ["red and gold", "blue and white", "green and yellow",
                         "purple and gold", "orange and white", "black and gold",
                         "red and white", "green and white"]
        badge_styles = ["starburst explosion shape", "circular seal stamp",
                        "ribbon banner label", "shield badge shape",
                        "rounded rectangle tag", "hexagon badge shape"]

        for offer_type, offers in OFFER_LOGOS.items():
            for offer in offers:
                for color in color_schemes:
                    for badge in badge_styles[:4]:
                        p = (f"{offer} as {badge}, {color} color scheme, {VECTOR_SUFFIX}")
                        prompts.append({"category": "offer_logos", "subcategory": offer_type,
                                        "prompt": p, "seed": random.randint(1, 999999)})
        return prompts

    # ─── FURNITURE ───────────────────────────
    def generate_furniture_prompts(self):
        prompts = []
        materials = ["solid oak wood grain visible", "dark mahogany polished",
                     "white painted clean", "natural rattan woven",
                     "brushed stainless steel", "powder coated black metal",
                     "light bamboo natural", "rich teak wood oiled",
                     "dark walnut wood", "light Scandinavian pine"]
        conditions = ["brand new showroom condition", "modern minimalist design",
                      "vintage antique style", "rustic farmhouse style"]

        for furn_type, items in FURNITURE.items():
            for item in items:
                for material in materials:
                    for condition in conditions:
                        p = self.make_prompt(f"{item}, {material}, {condition}")
                        prompts.append({"category": "furniture", "subcategory": furn_type,
                                        "prompt": p, "seed": random.randint(1, 999999)})
        return prompts

    # ─── TOOLS ───────────────────────────────
    def generate_tools_prompts(self):
        prompts = []
        conditions = ["brand new unused", "professional grade heavy duty",
                      "premium quality finish", "stainless steel polished",
                      "chrome plated gleaming", "ergonomic design grip"]
        views = ["front view flat lay", "45 degree angle view", "close-up detail macro"]

        for tool_type, tools in TOOLS.items():
            for tool in tools:
                for condition in conditions:
                    for view in views:
                        p = self.make_prompt(f"{tool}, {condition}, {view}")
                        prompts.append({"category": "tools", "subcategory": tool_type,
                                        "prompt": p, "seed": random.randint(1, 999999)})
        return prompts

    # ─── FESTIVALS ───────────────────────────
    def generate_festival_prompts(self):
        prompts = []
        photo_styles = ["studio product photography", "editorial photography",
                        "close-up detail photography", "lifestyle photography"]
        moods = ["festive warm glow", "traditional authentic feel", "vibrant colorful bright"]

        for fest_type, items in FESTIVALS.items():
            for item in items:
                for style in photo_styles:
                    for mood in moods:
                        p = self.make_prompt(f"{item}, {style}, {mood}")
                        prompts.append({"category": "festivals", "subcategory": fest_type,
                                        "prompt": p, "seed": random.randint(1, 999999)})
        return prompts

    # ─── BIRDS & INSECTS ────────────────────
    def generate_bird_insect_prompts(self):
        prompts = []
        contexts = ["perched on natural branch", "in alert natural pose",
                    "detailed portrait close-up", "full body side view",
                    "wings spread open display", "close-up head and eye detail",
                    "in mid flight captured", "resting peacefully"]

        for creature_type, creatures in BIRDS_INSECTS.items():
            for creature in creatures:
                for context in contexts:
                    p = self.make_prompt(f"{creature}, {context}, wildlife photography")
                    prompts.append({"category": "birds_insects", "subcategory": creature_type,
                                    "prompt": p, "seed": random.randint(1, 999999)})
        return prompts

    # ─── JEWELLERY ───────────────────────────
    def generate_jewellery_prompts(self):
        prompts = []
        finishes = ["mirror polished gold", "matte brushed gold", "diamonds sparkling faceted",
                    "antique oxidized finish", "modern minimal design",
                    "oxidized dark silver", "rose gold warm tone",
                    "two-tone gold and silver"]
        contexts = ["on white marble surface", "floating isolated clean",
                    "on black velvet display cushion", "extreme macro close-up"]

        for jewel_type, jewels in JEWELLERY.items():
            for jewel in jewels:
                for finish in finishes:
                    for context in contexts:
                        p = self.make_prompt(f"{jewel}, {finish}, {context}")
                        prompts.append({"category": "jewellery", "subcategory": jewel_type,
                                        "prompt": p, "seed": random.randint(1, 999999)})
        return prompts

    # ─── ANIMALS ─────────────────────────────
    def generate_animal_prompts(self):
        prompts = []
        poses = ["standing side profile view", "facing forward looking at camera",
                 "in natural relaxed pose", "close-up portrait head detail",
                 "full body view isolated", "resting calm relaxed",
                 "alert and attentive stance", "playful dynamic pose"]
        photo_approaches = ["wildlife photography style", "studio animal portrait",
                            "nature documentary quality"]

        for animal_type, animals in ANIMALS.items():
            for animal in animals:
                for pose in poses:
                    for approach in photo_approaches:
                        p = self.make_prompt(f"{animal}, {pose}, {approach}")
                        prompts.append({"category": "animals", "subcategory": animal_type,
                                        "prompt": p, "seed": random.randint(1, 999999)})
        return prompts

    # ─── ELECTRONICS (NEW) ──────────────────
    def generate_electronics_prompts(self):
        prompts = []
        angles = ["front view showing screen", "45 degree angle hero shot",
                  "side profile thin view", "top down flat lay"]

        for elec_type, items in ELECTRONICS.items():
            for item in items:
                for angle in angles:
                    p = self.make_prompt(f"{item}, {angle}, tech product photography")
                    prompts.append({"category": "electronics", "subcategory": elec_type,
                                    "prompt": p, "seed": random.randint(1, 999999)})
        return prompts

    # ─── SPICES (NEW) ───────────────────────
    def generate_spice_prompts(self):
        prompts = []
        for spice_type, spices in SPICES.items():
            for spice in spices:
                for context in SPICE_CONTEXT:
                    p = self.make_prompt(f"{spice}, {context}, aromatic food photography")
                    prompts.append({"category": "spices", "subcategory": spice_type,
                                    "prompt": p, "seed": random.randint(1, 999999)})
        return prompts

    # ─── BEVERAGES (NEW) ────────────────────
    def generate_beverage_prompts(self):
        prompts = []
        moods = ["warm cozy atmosphere", "refreshing cool tone",
                 "elegant fine dining style", "rustic authentic style"]

        for bev_type, beverages in BEVERAGES.items():
            for beverage in beverages:
                for mood in moods:
                    p = self.make_prompt(f"{beverage}, {mood}, beverage photography")
                    prompts.append({"category": "beverages", "subcategory": bev_type,
                                    "prompt": p, "seed": random.randint(1, 999999)})
        return prompts

    # ─── SHOES (NEW) ────────────────────────
    def generate_shoe_prompts(self):
        prompts = []
        views = ["side profile single shoe", "pair from front angled",
                 "45 degree hero shot pair", "sole detail close-up"]

        for shoe_type, shoes in SHOES.items():
            for shoe in shoes:
                for view in views:
                    p = self.make_prompt(f"{shoe}, {view}, footwear product photography")
                    prompts.append({"category": "shoes", "subcategory": shoe_type,
                                    "prompt": p, "seed": random.randint(1, 999999)})
        return prompts

    # ─── BAGS (NEW) ─────────────────────────
    def generate_bag_prompts(self):
        prompts = []
        views = ["front view standing upright", "45 degree angle showing depth",
                 "open showing interior compartments", "flat lay top down"]

        for bag_type, bags in BAGS.items():
            for bag in bags:
                for view in views:
                    p = self.make_prompt(f"{bag}, {view}, luxury product photography")
                    prompts.append({"category": "bags", "subcategory": bag_type,
                                    "prompt": p, "seed": random.randint(1, 999999)})
        return prompts

    # ─── COSMETICS (NEW) ────────────────────
    def generate_cosmetics_prompts(self):
        prompts = []
        views = ["front product shot clean", "45 degree beauty shot",
                 "macro detail showing texture", "arranged flat lay composition"]

        for cos_type, items in COSMETICS.items():
            for item in items:
                for view in views:
                    p = self.make_prompt(f"{item}, {view}, beauty product photography")
                    prompts.append({"category": "cosmetics", "subcategory": cos_type,
                                    "prompt": p, "seed": random.randint(1, 999999)})
        return prompts

    # ─── SPORTS (NEW) ───────────────────────
    def generate_sports_prompts(self):
        prompts = []
        views = ["front view on surface", "dramatic hero shot angle",
                 "close-up detail texture", "group arrangement flat lay"]

        for sport_type, items in SPORTS.items():
            for item in items:
                for view in views:
                    p = self.make_prompt(f"{item}, {view}, sports product photography")
                    prompts.append({"category": "sports", "subcategory": sport_type,
                                    "prompt": p, "seed": random.randint(1, 999999)})
        return prompts

    # ─── MUSICAL INSTRUMENTS (NEW) ──────────
    def generate_music_prompts(self):
        prompts = []
        views = ["full instrument front view", "45 degree angle showing detail",
                 "close-up detail of craftsmanship", "dramatic side profile"]

        for inst_type, instruments in MUSICAL_INSTRUMENTS.items():
            for instrument in instruments:
                for view in views:
                    p = self.make_prompt(f"{instrument}, {view}, musical instrument photography")
                    prompts.append({"category": "music", "subcategory": inst_type,
                                    "prompt": p, "seed": random.randint(1, 999999)})
        return prompts

    # ─── POOJA ITEMS (NEW) ──────────────────
    def generate_pooja_prompts(self):
        prompts = []
        finishes = ["polished gleaming finish", "antique aged patina",
                    "brand new temple quality", "traditional handcrafted detail"]

        for pooja_type, items in POOJA_ITEMS.items():
            for item in items:
                for finish in finishes:
                    p = self.make_prompt(f"{item}, {finish}, devotional product photography")
                    prompts.append({"category": "pooja_items", "subcategory": pooja_type,
                                    "prompt": p, "seed": random.randint(1, 999999)})
        return prompts

    # ─── CLOTHING (NEW) ─────────────────────
    def generate_clothing_prompts(self):
        prompts = []
        views = ["neatly folded on surface", "draped showing fabric flow",
                 "flat lay full garment view", "close-up fabric texture detail"]

        for cloth_type, items in CLOTHING.items():
            for item in items:
                for view in views:
                    p = self.make_prompt(f"{item}, {view}, fashion product photography")
                    prompts.append({"category": "clothing", "subcategory": cloth_type,
                                    "prompt": p, "seed": random.randint(1, 999999)})
        return prompts

    # ─── MEDICAL (NEW) ─────────────────────
    def generate_medical_prompts(self):
        prompts = []
        views = ["front product shot clean", "45 degree angle detail",
                 "flat lay arrangement", "close-up macro detail"]

        for med_type, items in MEDICAL.items():
            for item in items:
                for view in views:
                    p = self.make_prompt(f"{item}, {view}, medical product photography")
                    prompts.append({"category": "medical", "subcategory": med_type,
                                    "prompt": p, "seed": random.randint(1, 999999)})
        return prompts

    # ─── STATIONERY (NEW) ──────────────────
    def generate_stationery_prompts(self):
        prompts = []
        views = ["front view on desk surface", "45 degree angle artistic",
                 "flat lay arranged composition", "close-up detail shot"]

        for stat_type, items in STATIONERY.items():
            for item in items:
                for view in views:
                    p = self.make_prompt(f"{item}, {view}, stationery product photography")
                    prompts.append({"category": "stationery", "subcategory": stat_type,
                                    "prompt": p, "seed": random.randint(1, 999999)})
        return prompts

    # ═════════════════════════════════════════
    # GENERATE ALL PROMPTS
    # ═════════════════════════════════════════

    def generate_all_prompts(self):
        """Generate ALL unique prompts - 100% photorealistic"""
        print("🎨 Generating all ultra-realistic prompts...")
        all_prompts = []

        generators = [
            ("Food", self.generate_food_prompts),
            ("Fruits & Vegetables", self.generate_fruit_veg_prompts),
            ("Flowers", self.generate_flower_prompts),
            ("Vehicles", self.generate_vehicle_prompts),
            ("Nature/Trees", self.generate_nature_prompts),
            ("Pots/Vessels", self.generate_pots_prompts),
            ("Smoke/Effects", self.generate_smoke_prompts),
            ("Sky/Celestial", self.generate_sky_prompts),
            ("Cliparts 3D", self.generate_clipart_prompts),
            ("Frames/Borders", self.generate_frame_prompts),
            ("Offer Logos", self.generate_offer_logo_prompts),
            ("Furniture", self.generate_furniture_prompts),
            ("Tools", self.generate_tools_prompts),
            ("Festivals", self.generate_festival_prompts),
            ("Birds/Insects", self.generate_bird_insect_prompts),
            ("Jewellery", self.generate_jewellery_prompts),
            ("Animals", self.generate_animal_prompts),
            ("Electronics", self.generate_electronics_prompts),
            ("Spices", self.generate_spice_prompts),
            ("Beverages", self.generate_beverage_prompts),
            ("Shoes", self.generate_shoe_prompts),
            ("Bags", self.generate_bag_prompts),
            ("Cosmetics", self.generate_cosmetics_prompts),
            ("Sports", self.generate_sports_prompts),
            ("Musical Instruments", self.generate_music_prompts),
            ("Pooja Items", self.generate_pooja_prompts),
            ("Clothing", self.generate_clothing_prompts),
            ("Medical", self.generate_medical_prompts),
            ("Stationery", self.generate_stationery_prompts),
        ]

        for name, gen_func in generators:
            prev = len(all_prompts)
            all_prompts.extend(gen_func())
            print(f"  ✅ {name}: {len(all_prompts) - prev}")

        # ── Seed Multiplier: Each prompt gets 2 different seeds ──
        extended = []
        micro_variations = [
            "extremely detailed surface texture",
            "ultra sharp tack focus",
            "fine grain material detail visible",
            "crisp clean photographic quality",
            "true to life color accuracy"
        ]
        for item in all_prompts:
            extended.append(item)  # Original
            new_item = dict(item)
            extra = random.choice(micro_variations)
            new_item["prompt"] = item["prompt"].replace(
                BASE_SUFFIX, f"{extra}, {BASE_SUFFIX}"
            )
            new_item["seed"] = random.randint(100000, 999999)
            extended.append(new_item)

        all_prompts = extended
        print(f"\n  🔁 After seed-multiplier: {len(all_prompts)} unique prompts")

        # Shuffle for variety across batches
        random.shuffle(all_prompts)

        # Add index and metadata
        for i, p in enumerate(all_prompts):
            p["index"] = i
            p["filename"] = f"img_{i:06d}.png"
            p["status"] = "pending"

        print(f"\n🎯 TOTAL PROMPTS GENERATED: {len(all_prompts)}")
        return all_prompts

    def save_prompts(self, output_dir="prompts/splits"):
        """
        Save prompts split by category into prompts/splits/<category>.json
        Each file is well under GitHub 100MB limit.
        Use load_all_prompts() to reload them as a single list.
        """
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        prompts = self.generate_all_prompts()

        # Group by category (replace / with _ for filenames)
        by_cat = {}
        for p in prompts:
            key = p.get("category", "misc").replace("/", "_")
            by_cat.setdefault(key, []).append(p)

        saved_files = []
        for cat, items in by_cat.items():
            fpath = out / f"{cat}.json"
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(items, f, indent=2, ensure_ascii=False)
            size_kb = fpath.stat().st_size / 1024
            print(f"  💾 {cat}.json  →  {len(items)} prompts  ({size_kb:.1f} KB)")
            saved_files.append(str(fpath))

        # Write index so loaders know which files exist
        index = {"total": len(prompts), "categories": list(by_cat.keys()),
                 "files": [f"{c}.json" for c in by_cat]}
        with open(out / "index.json", "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2, ensure_ascii=False)

        print(f"\n✅ Saved {len(prompts)} prompts across {len(by_cat)} category files in '{output_dir}/'")
        print("📋 index.json written — use load_all_prompts() to reload all.")
        return output_dir


def load_all_prompts(splits_dir="prompts/splits"):
    """
    Load all category split JSON files and return a single merged list.
    Works as a drop-in replacement for json.load(open('all_prompts.json')).
    """
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
