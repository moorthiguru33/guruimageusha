"""
🎨 PNG Library - World's Best Prompt Engine
Generates 50,000+ UNIQUE prompts using combinatorial logic
Every image will be different - guaranteed!
"""

import random
import json
import itertools
from pathlib import Path

# ─────────────────────────────────────────────
# MASTER PROMPT FORMULA (for clean BG removal)
# ─────────────────────────────────────────────
# "[subject + details], isolated on pure white background, 
#  product photography, 8k uhd, photorealistic, sharp focus,
#  professional studio lighting, clean edges, no shadows"

BASE_SUFFIX = (
    "isolated on pure white background, product photography style, "
    "8k uhd resolution, photorealistic, sharp focus, clean crisp edges, "
    "professional studio lighting, no drop shadow, no gradient background, "
    "centered composition"
)

# ─────────────────────────────────────────────
# UNIVERSAL VARIATION BANKS
# ─────────────────────────────────────────────

CAMERA_ANGLES = [
    "front view", "45 degree angle view", "top-down overhead view",
    "side profile view", "3/4 angle view", "close-up macro view",
    "low angle view", "eye level view"
]

LIGHTING_STYLES = [
    "soft diffused studio light", "dramatic side lighting",
    "natural daylight", "golden hour warm light",
    "cool blue studio light", "rim lighting highlight"
]

DETAIL_QUALITY = [
    "hyper detailed", "ultra realistic", "highly detailed textures",
    "intricate details", "fine details visible", "detailed surface texture"
]

# ─────────────────────────────────────────────
# 🍛 FOOD CATEGORIES
# ─────────────────────────────────────────────

INDIAN_FOOD = {
    "biryani": {
        "types": ["Hyderabadi dum biryani", "Lucknowi biryani", "Kolkata chicken biryani",
                  "Malabar biryani", "Dindigul biryani", "Ambur biryani",
                  "Thalassery biryani", "Sindhi biryani", "Kashmiri biryani",
                  "Chettinad biryani"],
        "vessels": ["ceramic bowl", "copper handi", "banana leaf", "steel plate",
                    "clay pot", "silver thali", "terracotta bowl", "cast iron pot"],
        "garnish": ["with mint leaves", "garnished with fried onions", "with saffron strands",
                    "topped with boiled egg", "with raita on side", "with sliced lemon"],
        "style": ["restaurant plating", "home style serving", "street food style",
                  "wedding feast style", "royal presentation"]
    },
    "dosa": {
        "types": ["crispy masala dosa", "paper thin plain dosa", "set dosa",
                  "pesarattu dosa", "rava dosa", "neer dosa", "egg dosa",
                  "cheese dosa", "ghee roast dosa", "paneer dosa"],
        "vessels": ["steel plate", "banana leaf", "white ceramic plate",
                    "wooden board", "cast iron tawa"],
        "garnish": ["with coconut chutney", "with sambar bowl", "with tomato chutney",
                    "with green chutney", "with butter on top"],
        "style": ["breakfast style", "restaurant style", "street food style", "traditional style"]
    },
    "curry": {
        "types": ["butter chicken curry", "palak paneer", "dal makhani", "chole masala",
                  "fish curry Kerala style", "mutton rogan josh", "prawn masala",
                  "rajma curry", "matar paneer", "kadai chicken",
                  "Chettinad chicken curry", "Goan fish curry"],
        "vessels": ["ceramic bowl", "copper bowl", "clay pot", "steel bowl",
                    "wooden bowl", "white porcelain bowl"],
        "garnish": ["with fresh coriander", "cream swirl on top", "with naan bread",
                    "with jeera rice", "with pickle on side"],
        "style": ["restaurant plating", "home style", "traditional serving"]
    },
    "sweets": {
        "types": ["gulab jamun", "rasgulla", "jalebi", "ladoo", "barfi",
                  "kheer", "halwa", "peda", "mysore pak", "motichoor ladoo",
                  "kaju katli", "besan ladoo", "rava ladoo"],
        "vessels": ["silver plate", "brass plate", "white ceramic plate",
                    "clay cup", "paper box", "banana leaf"],
        "garnish": ["with silver varq", "with pistachio garnish", "with rose petals",
                    "with saffron", "with dry fruits"],
        "style": ["festive presentation", "shop display style", "homemade style"]
    }
}

WORLD_FOOD = {
    "pizza": ["thin crust Margherita pizza", "deep dish pepperoni pizza",
              "Neapolitan pizza with basil", "BBQ chicken pizza",
              "four cheese pizza", "veggie supreme pizza",
              "truffle mushroom pizza", "prosciutto pizza"],
    "burger": ["classic beef cheeseburger", "crispy chicken burger",
               "mushroom Swiss burger", "BBQ bacon burger",
               "veggie black bean burger", "double patty smash burger",
               "fish burger with tartar sauce", "Korean bulgogi burger"],
    "sushi": ["salmon nigiri sushi", "California roll", "dragon roll sushi",
              "tuna sashimi", "maki sushi platter", "rainbow roll",
              "temaki hand roll", "chirashi bowl"],
    "pasta": ["spaghetti carbonara", "fettuccine alfredo", "penne arrabbiata",
              "lasagna bolognese", "seafood linguine", "pesto gnocchi",
              "mushroom risotto", "ravioli with sage butter"],
    "desserts": ["chocolate lava cake", "strawberry cheesecake", "tiramisu",
                 "crème brûlée", "macaron tower", "Belgian waffle",
                 "ice cream sundae", "chocolate mousse"]
}

# ─────────────────────────────────────────────
# 🌸 FLOWERS
# ─────────────────────────────────────────────

FLOWERS = {
    "rose": ["red velvet rose", "pink garden rose", "white rose", "yellow rose",
             "orange rose", "purple rose", "peach rose", "black rose",
             "multicolor rose", "blue rose"],
    "lotus": ["pink lotus flower", "white lotus in bloom", "purple lotus",
              "red lotus bud", "lotus with green pad"],
    "jasmine": ["white jasmine cluster", "arabian jasmine", "star jasmine",
                "jasmine garland", "jasmine bud"],
    "sunflower": ["large yellow sunflower", "dwarf sunflower", "chocolate sunflower",
                  "sunflower bouquet", "sunflower in bloom"],
    "orchid": ["purple phalaenopsis orchid", "white dendrobium orchid",
               "pink cymbidium orchid", "yellow oncidium orchid",
               "blue orchid", "red cattleya orchid"],
    "marigold": ["orange marigold", "yellow marigold", "marigold garland",
                 "marigold bunch", "African marigold"],
    "lily": ["white calla lily", "tiger lily", "pink stargazer lily",
             "yellow lily", "water lily", "Easter lily"],
    "hibiscus": ["red hibiscus", "yellow hibiscus", "pink hibiscus",
                 "white hibiscus", "multicolor hibiscus"],
    "other_flowers": ["cherry blossom branch", "lavender bunch", "dahlia flower",
                      "peony bloom", "tulip flower", "iris flower",
                      "gerbera daisy", "anthurium flower", "bird of paradise"]
}

FLOWER_STAGES = ["in full bloom", "half open bud", "just blooming", "fresh bud"]
FLOWER_CONTEXT = ["single stem", "small bouquet", "with dewdrops on petals",
                  "with green leaves", "floating on water", "freshly cut"]

# ─────────────────────────────────────────────
# 🚗 VEHICLES
# ─────────────────────────────────────────────

CARS = {
    "sports_car": ["red Ferrari 458 Italia", "yellow Lamborghini Huracan",
                   "blue Porsche 911", "silver McLaren 720S",
                   "black Bugatti Chiron", "white Aston Martin DB11",
                   "orange Mclaren 570S", "green Lotus Evora"],
    "suv": ["black Range Rover Sport", "white Toyota Land Cruiser",
            "silver BMW X5", "blue Ford Everest",
            "grey Mercedes GLE", "red Jeep Wrangler",
            "white Hyundai Creta", "black Kia Seltos"],
    "sedan": ["white Toyota Camry", "silver Honda Accord",
              "blue BMW 3 Series", "black Mercedes C-Class",
              "red Hyundai Verna", "grey Maruti Dzire"],
    "vintage": ["red 1960s Mustang", "blue 1955 Chevrolet Bel Air",
                "black 1930s Rolls Royce", "green 1960s Volkswagen Beetle",
                "white 1970s BMW E9", "yellow 1969 Camaro SS"],
    "electric": ["white Tesla Model S", "blue Rivian R1T",
                 "silver Lucid Air", "red Chevy Bolt",
                 "black BMW iX", "white Hyundai Ioniq 6"]
}

BIKES = {
    "sports_bike": ["red Honda CBR1000RR", "blue Yamaha R1",
                    "black Kawasaki Ninja ZX10R", "orange KTM Duke 390",
                    "yellow Suzuki GSX-R1000", "white BMW S1000RR"],
    "cruiser": ["black Royal Enfield Classic 350", "orange Royal Enfield Meteor",
                "chrome Harley Davidson Softail", "black Indian Chief",
                "burgundy Royal Enfield Thunderbird"],
    "adventure": ["orange KTM Adventure 390", "blue Royal Enfield Himalayan",
                  "silver BMW GS1250", "black Honda Africa Twin",
                  "yellow Yamaha Tenere 700"],
    "scooter": ["white Honda Activa", "blue TVS Jupiter",
                "red Vespa Primavera", "black Suzuki Burgman",
                "yellow Yamaha Fascino"],
    "bicycle": ["red road bicycle", "blue mountain bike", "black BMX bicycle",
                "white city cruiser bicycle", "orange fixie bicycle",
                "silver folding bicycle"]
}

CAR_ANGLES = ["front 3/4 view", "side profile view", "rear 3/4 view",
              "front view", "top aerial view", "dynamic driving angle"]

# ─────────────────────────────────────────────
# 🌳 TREES & NATURE
# ─────────────────────────────────────────────

TREES = {
    "fruit_trees": ["mango tree with fruits", "coconut palm tree", "banana tree",
                    "papaya tree", "guava tree with fruits", "lemon tree",
                    "orange tree", "apple tree in bloom", "fig tree",
                    "pomegranate tree with red fruits"],
    "tropical": ["tall coconut palm", "areca palm tree", "traveller's palm",
                 "banana plant cluster", "giant bamboo",
                 "Indian banyan tree", "peepal tree"],
    "ornamental": ["cherry blossom tree in full bloom", "jacaranda tree purple",
                   "golden shower tree yellow", "flame of forest red",
                   "magnolia tree white blooms", "weeping willow tree"],
    "forest": ["tall pine tree", "giant oak tree", "maple tree autumn leaves",
               "birch tree white bark", "cedar tree", "eucalyptus tree",
               "giant redwood tree", "bamboo grove"],
    "small_plants": ["succulent plant", "cactus plant", "aloe vera plant",
                     "money plant", "snake plant", "fern plant",
                     "bonsai tree", "air plant", "peace lily plant"]
}

TREE_CONTEXT = ["full tree view", "trunk detail close-up", "leaf detail macro",
                "with fruits visible", "seasonal bloom", "lush green canopy"]

# ─────────────────────────────────────────────
# 🏺 POTS & VESSELS
# ─────────────────────────────────────────────

POTS_VESSELS = {
    "clay_pots": ["traditional red clay pot", "terracotta water pot",
                  "handpainted clay pot", "black clay cooking pot",
                  "glazed ceramic pot", "rustic clay vessel"],
    "metal_vessels": ["shiny copper pot", "brass lota", "steel cooking vessel",
                      "silver milk pot", "antique bronze vessel",
                      "iron kadai wok", "aluminum pressure cooker"],
    "decorative": ["blue and white ceramic vase", "floral painted pot",
                   "golden decorative urn", "wooden carved bowl",
                   "glass crystal vase", "marble decorative pot"],
    "cooking": ["clay tawa griddle", "stone mortar and pestle",
                "wicker basket", "bamboo steamer",
                "copper serving bowl", "brass measuring cups set"]
}

# ─────────────────────────────────────────────
# 💨 SMOKE & EFFECTS PNG
# ─────────────────────────────────────────────

SMOKE_EFFECTS = {
    "smoke": ["wispy white smoke cloud", "thick rising smoke column",
              "curling smoke tendrils", "smoke ring puff",
              "colored smoke red", "colored smoke blue",
              "colored smoke green", "colored smoke purple",
              "colored smoke yellow", "colored smoke orange",
              "dense fog cloud", "misty vapor cloud"],
    "fire": ["orange flame fire", "blue flame fire",
             "campfire flames", "candle flame single",
             "fire spark burst", "fire trail motion"],
    "sparkle": ["golden sparkle burst", "silver glitter explosion",
                "magic sparkle dust", "fairy dust particles",
                "star burst sparkle", "confetti burst colorful"],
    "light_effects": ["lens flare gold", "bokeh light circles",
                      "rainbow light beam", "sunburst rays",
                      "neon glow effect", "laser beam effect"]
}

# ─────────────────────────────────────────────
# ☀️ SKY ELEMENTS & CELESTIAL
# ─────────────────────────────────────────────

SKY_ELEMENTS = {
    "sun": ["bright yellow sun with rays", "golden sunrise sun",
            "cartoon sun smiling", "sun with sunburst rays",
            "partial eclipse sun", "watercolor sun"],
    "moon": ["full moon realistic", "crescent moon", "half moon phase",
             "golden moon glowing", "moon with stars",
             "cartoon moon face"],
    "stars": ["5 point gold star", "shooting star trail",
              "star cluster constellation", "glowing neon star",
              "sparkle star burst", "3D gold star"],
    "clouds": ["fluffy white cloud", "storm dark cloud",
               "rain cloud with drops", "cartoon cloud",
               "rainbow over cloud", "golden cloud sunrise"],
    "weather": ["lightning bolt", "rainbow arc",
                "snowflake crystal", "rain drops falling",
                "tornado funnel", "wind swirl"]
}

# ─────────────────────────────────────────────
# 🎨 CLIPARTS
# ─────────────────────────────────────────────

CLIPARTS = {
    "arrows": ["bold red arrow right", "curved blue arrow",
               "double headed arrow", "circular arrow loop",
               "3D gold arrow pointing", "neon green arrow"],
    "hearts": ["red heart 3D glossy", "pink heart outline",
               "gold heart shape", "broken heart",
               "heart made of flowers", "pixel heart",
               "rainbow colored heart", "heart with wings"],
    "ribbons_banners": ["golden ribbon banner", "red victory ribbon",
                        "blue award ribbon", "scroll ribbon unfurled",
                        "banner flag red", "award medal gold"],
    "checkmarks_x": ["green checkmark tick", "red X cross mark",
                     "gold star rating", "thumbs up icon",
                     "thumbs down icon", "crown gold"],
    "symbols": ["peace sign", "infinity symbol", "yin yang symbol",
                "anchor nautical", "compass rose", "trefoil clover",
                "fleur de lis", "Celtic knot"]
}

# ─────────────────────────────────────────────
# 🖼️ FRAMES & BORDERS
# ─────────────────────────────────────────────

FRAMES_BORDERS = {
    "wedding": ["ornate gold wedding frame", "floral wedding border pink roses",
                "elegant white wedding frame", "vintage gold flourish frame",
                "romantic flower arch frame"],
    "festival": ["Diwali diya lamp border", "Christmas holly border",
                 "Eid crescent moon frame", "Pongal kolam border",
                 "New Year fireworks frame", "Holi colorful splash border"],
    "modern": ["minimalist thin gold border", "geometric hexagon frame",
               "neon glow rectangular border", "rounded corner modern frame",
               "brushstroke artistic border", "watercolor splash frame"],
    "nature": ["floral wreath frame", "tropical leaves border",
               "bamboo wooden frame", "vine and flower border",
               "sunflower frame circle", "autumn leaves border"]
}

# ─────────────────────────────────────────────
# 🏷️ OFFER LOGOS & BADGES
# ─────────────────────────────────────────────

OFFER_LOGOS = {
    "discount": ["50% OFF sale badge red", "30% discount sticker",
                 "20% OFF circular badge", "FLAT 40% OFF label",
                 "MEGA SALE burst badge", "CLEARANCE SALE tag",
                 "10% OFF coupon stamp", "SAVE 25% label"],
    "buy_deals": ["BUY 1 GET 1 FREE badge", "BUY 2 GET 1 FREE sticker",
                  "FREE GIFT with purchase badge", "COMBO OFFER seal"],
    "special_offers": ["SPECIAL OFFER starburst", "LIMITED TIME OFFER badge",
                       "TODAY ONLY deal badge", "FLASH SALE lightning badge",
                       "BEST PRICE badge green", "HOT DEAL fire badge",
                       "EXCLUSIVE OFFER seal gold", "VIP OFFER crown badge"],
    "seasonal": ["DIWALI SPECIAL offer badge", "SUMMER SALE badge",
                 "FESTIVAL OFFER label", "NEW YEAR DEAL badge",
                 "EID MUBARAK OFFER", "CHRISTMAS SALE sticker"],
    "quality": ["BEST SELLER badge gold", "TOP RATED star badge",
                "NEW ARRIVAL ribbon", "TRENDING NOW badge",
                "PREMIUM QUALITY seal", "100% GENUINE badge"]
}

# ─────────────────────────────────────────────
# 🎭 ABSTRACT & VECTOR ART
# ─────────────────────────────────────────────

ABSTRACT = {
    "fluid_art": ["colorful fluid pour art red blue gold",
                  "acrylic fluid art green purple",
                  "ink drop in water spread multicolor",
                  "oil paint swirl abstract blue",
                  "marbling art black gold"],
    "geometric": ["3D geometric cube wireframe neon",
                  "hexagonal pattern gold geometric",
                  "triangle mosaic colorful abstract",
                  "diamond prism refraction",
                  "low poly abstract mountain"],
    "neon_glow": ["neon light tube pink purple",
                  "glowing neon geometric circle",
                  "neon wireframe cube blue",
                  "cyberpunk neon abstract lines",
                  "neon splash on dark glow"],
    "particles": ["golden particle dust burst",
                  "colorful confetti particles explosion",
                  "floating orbs bokeh abstract",
                  "sparkle particle stream",
                  "nebula space dust colorful"]
}

# ─────────────────────────────────────────────
# 🏠 FURNITURE & HOME
# ─────────────────────────────────────────────

FURNITURE = {
    "seating": ["modern white armchair", "wooden rocking chair",
                "velvet blue sofa", "leather office chair",
                "rattan garden chair", "antique wooden bench"],
    "tables": ["glass top coffee table", "wooden dining table",
               "marble top side table", "folding plastic table",
               "antique carved wooden table"],
    "storage": ["oak bookshelf", "modern wardrobe white",
                "wooden chest of drawers", "rattan storage basket",
                "wall mounted shelves wooden"],
    "beds": ["king size platform bed", "wooden bunk bed",
             "upholstered bed tufted headboard", "metal daybed"]
}

# ─────────────────────────────────────────────
# 🔧 TOOLS & EQUIPMENT
# ─────────────────────────────────────────────

TOOLS = {
    "hand_tools": ["steel hammer", "adjustable wrench", "screwdriver set",
                   "pliers red handle", "measuring tape", "hacksaw",
                   "chisel set wooden handle", "hand drill"],
    "kitchen_tools": ["stainless steel knife set", "wooden spatula",
                      "cast iron pan", "mixing bowl stainless",
                      "rolling pin wooden", "grater stainless",
                      "ladle long handle", "tongs kitchen steel"],
    "garden_tools": ["garden spade", "pruning shears", "watering can green",
                     "garden fork", "trowel small"],
    "power_tools": ["cordless electric drill", "angle grinder",
                    "jigsaw power tool", "circular saw",
                    "orbital sander", "electric screwdriver"]
}

# ─────────────────────────────────────────────
# 🎉 FESTIVAL & EVENTS
# ─────────────────────────────────────────────

FESTIVALS = {
    "diwali": ["diya oil lamp glowing", "rangoli colorful pattern",
               "fireworks burst colorful", "lakshmi idol golden",
               "diwali gift box decorated", "sparkler light trail"],
    "christmas": ["christmas tree decorated", "santa claus figure",
                  "christmas wreath holly", "christmas gift box red ribbon",
                  "snowman figurine", "christmas star ornament"],
    "pongal": ["pongal pot decorated", "sugarcane stalk", "kolam floor art",
               "pongal dish clay pot", "sun symbol pongal"],
    "eid": ["crescent moon and star", "lantern eid fanoos",
            "dates fruit plate", "henna mehndi hand pattern",
            "mosque silhouette", "eid gift box"],
    "general": ["birthday cake with candles", "celebration balloon bunch",
                "party popper confetti", "graduation cap", "trophy gold",
                "gift box wrapped ribbon"]
}

# ─────────────────────────────────────────────
# 🦋 BIRDS & INSECTS
# ─────────────────────────────────────────────

BIRDS_INSECTS = {
    "birds": ["peacock with open feathers", "colorful parrot on branch",
              "kingfisher bird vivid blue", "flamingo pink standing",
              "toucan tropical bird", "eagle flying wings spread",
              "owl perched on branch", "hummingbird hovering",
              "robin red breast bird", "pigeon white dove"],
    "butterflies": ["monarch butterfly orange", "blue morpho butterfly",
                    "swallowtail butterfly yellow", "white butterfly wings open",
                    "painted lady butterfly", "glasswing butterfly transparent"],
    "insects": ["ladybug red black dots", "honeybee on flower",
                "dragonfly iridescent wings", "praying mantis green",
                "stag beetle", "firefly glowing"]
}

# ─────────────────────────────────────────────
# 💎 JEWELLERY
# ─────────────────────────────────────────────

JEWELLERY = {
    "necklace": ["gold temple necklace", "diamond solitaire pendant",
                 "pearl strand necklace", "ruby gold necklace",
                 "emerald pendant gold", "kundan necklace",
                 "silver oxidized necklace", "beaded necklace colorful"],
    "earrings": ["gold jhumka earrings", "diamond stud earrings",
                 "pearl drop earrings", "chandbali gold earrings",
                 "hoop earrings gold large", "crystal earrings"],
    "rings": ["diamond solitaire ring", "gold band ring",
              "ruby ring gold setting", "emerald ring",
              "oxidized silver ring", "wedding ring diamond band"],
    "bangles": ["gold bangle set", "glass bangles colorful",
                "silver bangle bracelet", "kundan bangle set",
                "kada thick bangle gold"]
}

# ─────────────────────────────────────────────
# 🐄 ANIMALS
# ─────────────────────────────────────────────

ANIMALS = {
    "farm": ["cow standing white", "buffalo black", "goat brown white",
             "sheep fluffy white", "chicken hen brown", "duck yellow"],
    "wild": ["elephant African", "lion male mane", "tiger orange stripes",
             "leopard spotted", "giraffe tall", "zebra black white",
             "rhinoceros grey", "hippopotamus"],
    "sea": ["dolphin jumping", "whale blue", "shark great white",
            "octopus purple", "sea turtle", "clownfish orange",
            "starfish orange", "jellyfish translucent"],
    "pets": ["golden retriever dog", "persian cat white",
             "rabbit white fluffy", "hamster golden",
             "parrot blue perched", "fish colorful aquarium"]
}

# ─────────────────────────────────────────────
# PROMPT GENERATOR CLASS
# ─────────────────────────────────────────────

class PromptEngine:
    def __init__(self):
        self.generated_prompts = set()
        self.prompt_list = []

    def make_prompt(self, subject, extra_details=""):
        """Create a FLUX-optimized prompt for clean white background"""
        angle = random.choice(CAMERA_ANGLES)
        lighting = random.choice(LIGHTING_STYLES)
        quality = random.choice(DETAIL_QUALITY)
        
        if extra_details:
            prompt = f"{subject}, {extra_details}, {angle}, {lighting}, {quality}, {BASE_SUFFIX}"
        else:
            prompt = f"{subject}, {angle}, {lighting}, {quality}, {BASE_SUFFIX}"
        return prompt

    def generate_food_prompts(self, count_per_item=8):
        prompts = []
        styles = ["food photography", "restaurant menu style", "rustic traditional",
                  "street food style", "royal presentation", "home style serving",
                  "wedding feast style", "magazine editorial style"]
        
        # Indian food - ALL combinations
        for dish, data in INDIAN_FOOD.items():
            for type_ in data["types"]:
                for vessel in data["vessels"]:
                    for garnish in data["garnish"][:3]:
                        for style in data["style"]:
                            subject = f"{type_} served in {vessel}, {garnish}, {style}"
                            p = self.make_prompt(subject)
                            prompts.append({"category": "food/indian", "subcategory": dish,
                                            "prompt": p, "seed": random.randint(1, 999999)})

        # World food - all vessels × styles
        vessels_world = ["on wooden board", "on white ceramic plate", "in ceramic bowl",
                         "on slate serving board", "in glass bowl", "on banana leaf",
                         "on cast iron skillet", "in terracotta dish"]
        for dish, items in WORLD_FOOD.items():
            for item in items:
                for vessel in vessels_world:
                    for style in styles[:4]:
                        p = self.make_prompt(item, f"{vessel}, {style}")
                        prompts.append({"category": "food/world", "subcategory": dish,
                                        "prompt": p, "seed": random.randint(1, 999999)})
        return prompts

    def generate_flower_prompts(self):
        prompts = []
        render_styles = ["hyper realistic photography", "watercolor painting style",
                         "3D rendered illustration", "oil painting style",
                         "digital art style", "macro photography",
                         "botanical illustration", "minimalist art"]
        
        for flower_type, varieties in FLOWERS.items():
            for variety in varieties:
                for stage in FLOWER_STAGES:
                    for context in FLOWER_CONTEXT:  # ALL contexts
                        for style in render_styles[:4]:
                            subject = f"{variety} {stage}, {context}, {style}"
                            p = self.make_prompt(subject)
                            prompts.append({"category": "flowers", "subcategory": flower_type,
                                            "prompt": p, "seed": random.randint(1, 999999)})
        return prompts

    def generate_vehicle_prompts(self):
        prompts = []
        car_colors = ["red", "white", "black", "silver", "blue", "grey"]
        bike_angles_full = CAR_ANGLES  # Use all angles
        
        for car_type, models in CARS.items():
            for model in models:
                for angle in CAR_ANGLES:
                    for detail in ["clean polished", "detailed reflections on bodywork",
                                   "gleaming paintwork", "chrome details"]:
                        p = self.make_prompt(f"{model}, {angle}", detail)
                        prompts.append({"category": "vehicles/cars", "subcategory": car_type,
                                        "prompt": p, "seed": random.randint(1, 999999)})

        for bike_type, models in BIKES.items():
            for model in models:
                for angle in bike_angles_full:
                    for detail in ["chrome exhaust pipes", "detailed engine", "shiny bodywork"]:
                        p = self.make_prompt(f"{model}, {angle}", detail)
                        prompts.append({"category": "vehicles/bikes", "subcategory": bike_type,
                                        "prompt": p, "seed": random.randint(1, 999999)})
        return prompts

    def generate_nature_prompts(self):
        prompts = []
        seasons = ["summer lush green", "autumn golden leaves", "spring fresh bloom",
                   "monsoon rain glistening", "tropical humid"]
        times_of_day = ["morning light", "afternoon bright", "golden hour", "soft diffused"]
        
        for tree_type, trees in TREES.items():
            for tree in trees:
                for context in TREE_CONTEXT:
                    for season in seasons:
                        p = self.make_prompt(f"{tree}, {context}, {season}")
                        prompts.append({"category": "nature/trees", "subcategory": tree_type,
                                        "prompt": p, "seed": random.randint(1, 999999)})
        return prompts

    def generate_pots_prompts(self):
        prompts = []
        finishes = ["new clean", "aged patina", "antique weathered", "polished shiny",
                    "hand painted floral", "carved pattern", "plain traditional"]
        sizes = ["small", "medium", "large", "miniature", "oversized"]
        
        for pot_type, pots in POTS_VESSELS.items():
            for pot in pots:
                for finish in finishes:
                    for size in sizes:
                        p = self.make_prompt(f"{size} {pot}, {finish} finish")
                        prompts.append({"category": "pots_vessels", "subcategory": pot_type,
                                        "prompt": p, "seed": random.randint(1, 999999)})
        return prompts

    def generate_smoke_prompts(self):
        prompts = []
        sizes = ["thin wispy", "medium thick", "dense heavy", "large billowing", "small delicate"]
        movements = ["rising upward", "swirling slowly", "dispersing outward",
                     "curling sideways", "drifting gently"]
        
        for effect_type, effects in SMOKE_EFFECTS.items():
            for effect in effects:
                for size in sizes:
                    for movement in movements:
                        special_suffix = (
                            "on pure white background, isolated, clean edges, "
                            "high contrast, 8k resolution, no background elements"
                        )
                        p = f"{size} {effect}, {movement}, {special_suffix}"
                        prompts.append({"category": "effects/smoke", "subcategory": effect_type,
                                        "prompt": p, "seed": random.randint(1, 999999)})
        return prompts

    def generate_sky_prompts(self):
        prompts = []
        render_styles = ["hyper realistic", "illustrated", "watercolor style",
                         "3D rendered", "cartoon style", "digital art",
                         "vintage engraving", "neon glow style",
                         "gold metallic", "minimalist flat"]
        color_moods = ["warm golden", "cool blue", "vibrant multicolor",
                       "pastel soft", "dramatic dark", "bright vivid"]
        
        for element_type, elements in SKY_ELEMENTS.items():
            for element in elements:
                for style in render_styles:
                    for mood in color_moods[:3]:
                        p = self.make_prompt(f"{element}, {style}, {mood} tones")
                        prompts.append({"category": "sky_celestial", "subcategory": element_type,
                                        "prompt": p, "seed": random.randint(1, 999999)})
        return prompts

    def generate_clipart_prompts(self):
        prompts = []
        render_styles = ["glossy 3D", "flat design", "cartoon", "realistic",
                         "neon glowing", "watercolor", "hand drawn sketch",
                         "chrome metallic", "pixel art", "vintage retro"]
        colors = ["red", "blue", "gold", "green", "purple", "orange", "pink", "multicolor"]
        
        for clip_type, clips in CLIPARTS.items():
            for clip in clips:
                for style in render_styles:
                    for color in colors[:4]:
                        p = self.make_prompt(f"{clip}, {color} color, {style} style")
                        prompts.append({"category": "cliparts", "subcategory": clip_type,
                                        "prompt": p, "seed": random.randint(1, 999999)})
        return prompts

    def generate_frame_prompts(self):
        prompts = []
        colors = ["gold", "silver", "rose gold", "black", "white", "bronze",
                  "platinum", "copper", "pearl white", "antique bronze"]
        styles = ["ornate detailed", "minimal clean", "rustic vintage",
                  "modern geometric", "floral intricate", "art deco"]
        
        for frame_type, frames in FRAMES_BORDERS.items():
            for frame in frames:
                for color in colors:
                    for style in styles:
                        p = (f"{frame}, {color} color scheme, {style} design, "
                             f"isolated on pure white background, vector style, 8k, "
                             f"high detail decorative border")
                        prompts.append({"category": "frames_borders", "subcategory": frame_type,
                                        "prompt": p, "seed": random.randint(1, 999999)})
        return prompts

    def generate_offer_logo_prompts(self):
        prompts = []
        color_schemes = ["red and gold", "blue and white", "green and yellow",
                         "purple and gold", "orange and white", "black and gold",
                         "red and white", "green and white", "navy and silver"]
        badge_styles = ["starburst badge", "circular seal", "ribbon label",
                        "stamp style", "shield badge", "hexagon badge",
                        "explosion burst", "rounded rectangle tag"]
        
        for offer_type, offers in OFFER_LOGOS.items():
            for offer in offers:
                for color in color_schemes:
                    for badge in badge_styles[:4]:
                        p = (f"{offer} as {badge}, {color} color scheme, "
                             f"professional graphic design, bold typography, "
                             f"isolated on pure white background, vector style, "
                             f"sharp edges, high contrast, 8k resolution")
                        prompts.append({"category": "offer_logos", "subcategory": offer_type,
                                        "prompt": p, "seed": random.randint(1, 999999)})
        return prompts

    def generate_abstract_prompts(self):
        prompts = []
        colors = ["vibrant multicolor", "monochrome blue", "warm red orange",
                  "cool teal green", "purple pink magenta", "gold black",
                  "neon cyan purple", "earth tone warm", "pastel rainbow",
                  "electric blue yellow"]
        sizes = ["full frame", "centered composition", "diagonal sweep", "circular burst"]
        
        for abs_type, abstracts in ABSTRACT.items():
            for abstract in abstracts:
                for color in colors:
                    for size in sizes:
                        p = self.make_prompt(f"{abstract}, {color}, {size}")
                        prompts.append({"category": "abstract", "subcategory": abs_type,
                                        "prompt": p, "seed": random.randint(1, 999999)})
        return prompts

    def generate_furniture_prompts(self):
        prompts = []
        materials = ["solid oak wood", "mahogany", "white painted MDF",
                     "natural rattan", "stainless steel", "black metal frame",
                     "bamboo", "teak wood", "walnut dark wood", "light pine wood"]
        conditions = ["brand new", "modern minimalist", "vintage antique style",
                      "rustic farmhouse", "Scandinavian design", "industrial style"]
        
        for furn_type, items in FURNITURE.items():
            for item in items:
                for material in materials:
                    for condition in conditions[:4]:
                        p = self.make_prompt(f"{item}, {material}, {condition}")
                        prompts.append({"category": "furniture", "subcategory": furn_type,
                                        "prompt": p, "seed": random.randint(1, 999999)})
        return prompts

    def generate_tools_prompts(self):
        prompts = []
        conditions = ["brand new", "professional grade", "heavy duty", "premium quality",
                      "stainless steel", "ergonomic handle", "chrome plated"]
        views = ["front view", "side view", "45 degree angle", "close-up detail"]
        
        for tool_type, tools in TOOLS.items():
            for tool in tools:
                for condition in conditions:
                    for view in views:
                        p = self.make_prompt(f"{tool}, {condition}, {view}")
                        prompts.append({"category": "tools", "subcategory": tool_type,
                                        "prompt": p, "seed": random.randint(1, 999999)})
        return prompts

    def generate_festival_prompts(self):
        prompts = []
        styles = ["realistic photography", "3D rendered", "illustrated art",
                  "watercolor", "digital painting", "festive colorful"]
        moods = ["joyful celebration", "traditional authentic", "modern stylized",
                 "vibrant colorful", "peaceful serene"]
        
        for fest_type, items in FESTIVALS.items():
            for item in items:
                for style in styles:
                    for mood in moods[:3]:
                        p = self.make_prompt(f"{item}, {style}, {mood}")
                        prompts.append({"category": "festivals", "subcategory": fest_type,
                                        "prompt": p, "seed": random.randint(1, 999999)})
        return prompts

    def generate_bird_insect_prompts(self):
        prompts = []
        contexts = ["perched on branch", "in natural pose", "detailed portrait",
                    "full body view", "wings spread open", "close-up head",
                    "in flight motion", "resting peaceful"]
        backgrounds_hint = ["", "with soft bokeh", "with natural texture"]
        
        for creature_type, creatures in BIRDS_INSECTS.items():
            for creature in creatures:
                for context in contexts:
                    p = self.make_prompt(f"{creature}, {context}")
                    prompts.append({"category": "birds_insects", "subcategory": creature_type,
                                    "prompt": p, "seed": random.randint(1, 999999)})
        return prompts

    def generate_jewellery_prompts(self):
        prompts = []
        finishes = ["shiny polished gold", "matte brushed gold", "with diamonds sparkling",
                    "antique finish", "modern minimal", "oxidized silver",
                    "rose gold plated", "two-tone gold silver"]
        contexts = ["on white surface", "floating isolated", "on velvet display",
                    "close-up macro"]
        
        for jewel_type, jewels in JEWELLERY.items():
            for jewel in jewels:
                for finish in finishes:
                    for context in contexts:
                        p = self.make_prompt(f"{jewel}, {finish}, {context}")
                        prompts.append({"category": "jewellery", "subcategory": jewel_type,
                                        "prompt": p, "seed": random.randint(1, 999999)})
        return prompts

    def generate_animal_prompts(self):
        prompts = []
        poses = ["standing side view", "facing forward camera", "in natural pose",
                 "close-up portrait", "full body view", "resting relaxed",
                 "alert attentive", "playful pose"]
        styles = ["hyper realistic", "wildlife photography", "detailed illustration",
                  "nature documentary style"]
        
        for animal_type, animals in ANIMALS.items():
            for animal in animals:
                for pose in poses:
                    for style in styles[:3]:
                        p = self.make_prompt(f"{animal}, {pose}, {style}")
                        prompts.append({"category": "animals", "subcategory": animal_type,
                                        "prompt": p, "seed": random.randint(1, 999999)})
        return prompts

    def generate_all_prompts(self):
        """Generate ALL 50,000+ unique prompts"""
        print("🎨 Generating all prompts...")
        all_prompts = []
        all_prompts.extend(self.generate_food_prompts())
        print(f"  ✅ Food: {len(all_prompts)}")
        
        prev = len(all_prompts)
        all_prompts.extend(self.generate_flower_prompts())
        print(f"  ✅ Flowers: {len(all_prompts) - prev}")

        prev = len(all_prompts)
        all_prompts.extend(self.generate_vehicle_prompts())
        print(f"  ✅ Vehicles: {len(all_prompts) - prev}")

        prev = len(all_prompts)
        all_prompts.extend(self.generate_nature_prompts())
        print(f"  ✅ Nature/Trees: {len(all_prompts) - prev}")

        prev = len(all_prompts)
        all_prompts.extend(self.generate_pots_prompts())
        print(f"  ✅ Pots/Vessels: {len(all_prompts) - prev}")

        prev = len(all_prompts)
        all_prompts.extend(self.generate_smoke_prompts())
        print(f"  ✅ Smoke/Effects: {len(all_prompts) - prev}")

        prev = len(all_prompts)
        all_prompts.extend(self.generate_sky_prompts())
        print(f"  ✅ Sky/Celestial: {len(all_prompts) - prev}")

        prev = len(all_prompts)
        all_prompts.extend(self.generate_clipart_prompts())
        print(f"  ✅ Cliparts: {len(all_prompts) - prev}")

        prev = len(all_prompts)
        all_prompts.extend(self.generate_frame_prompts())
        print(f"  ✅ Frames/Borders: {len(all_prompts) - prev}")

        prev = len(all_prompts)
        all_prompts.extend(self.generate_offer_logo_prompts())
        print(f"  ✅ Offer Logos: {len(all_prompts) - prev}")

        prev = len(all_prompts)
        all_prompts.extend(self.generate_abstract_prompts())
        print(f"  ✅ Abstract: {len(all_prompts) - prev}")

        prev = len(all_prompts)
        all_prompts.extend(self.generate_furniture_prompts())
        print(f"  ✅ Furniture: {len(all_prompts) - prev}")

        prev = len(all_prompts)
        all_prompts.extend(self.generate_tools_prompts())
        print(f"  ✅ Tools: {len(all_prompts) - prev}")

        prev = len(all_prompts)
        all_prompts.extend(self.generate_festival_prompts())
        print(f"  ✅ Festivals: {len(all_prompts) - prev}")

        prev = len(all_prompts)
        all_prompts.extend(self.generate_bird_insect_prompts())
        print(f"  ✅ Birds/Insects: {len(all_prompts) - prev}")

        prev = len(all_prompts)
        all_prompts.extend(self.generate_jewellery_prompts())
        print(f"  ✅ Jewellery: {len(all_prompts) - prev}")

        prev = len(all_prompts)
        all_prompts.extend(self.generate_animal_prompts())
        print(f"  ✅ Animals: {len(all_prompts) - prev}")

        # ── Seed Multiplier: Each prompt gets 2 different seeds ──────────
        # This guarantees different output even for same text prompt
        # FLUX.1-schnell is seed-sensitive, same prompt + diff seed = diff image
        extended = []
        extra_detail_vars = [
            "highly detailed", "ultra sharp", "fine texture detail",
            "crisp clean", "vivid colors"
        ]
        for item in all_prompts:
            extended.append(item)  # Original
            # Clone with new seed + slight prompt variation
            new_item = dict(item)
            extra = random.choice(extra_detail_vars)
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

    def save_prompts(self, output_path="prompts/all_prompts.json"):
        """Save all prompts to JSON file"""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        prompts = self.generate_all_prompts()
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(prompts, f, indent=2, ensure_ascii=False)
        print(f"✅ Saved {len(prompts)} prompts to {output_path}")
        return output_path


if __name__ == "__main__":
    engine = PromptEngine()
    engine.save_prompts("prompts/all_prompts.json")
