# PNG Library — Complete Setup Guide
## World's Biggest PNG Library (50,000+ Images) | FLUX.2 Quality

---

## FLUX.2 Model Strategy (Important!)

| Model          | VRAM    | Free? | Quality  | Our Choice |
|----------------|---------|-------|----------|------------|
| FLUX.2 [dev]   | 90 GB   | No    | Max      | Too heavy  |
| FLUX.2 [max]   | API only| No    | Max      | Paid API   |
| FLUX.2 [klein] 4B | ~13 GB | YES (Apache 2.0) | Excellent | CHOSEN |
| FLUX.2 [klein] 9B | ~20 GB | Non-commercial | Better   | Needs A100 |

We use FLUX.2 [klein] 4B because:
  - Apache 2.0 = commercial use FREE
  - Fits in Kaggle T4 (16 GB VRAM)
  - Superior to FLUX.1-schnell
  - Sub-second generation capability

Pipeline: FLUX.2 [klein] 4B (2048x2048) -> Real-ESRGAN x2 (4096x4096) -> BRIA-RMBG-2.0 (transparent PNG)

---

## GITHUB SECRETS SETUP

GitHub Repository -> Settings -> Secrets and Variables -> Actions -> New secret

| Secret Name          | Value                 |
|----------------------|-----------------------|
| GOOGLE_CLIENT_ID     | your_client_id        |
| GOOGLE_CLIENT_SECRET | your_client_secret    |
| GOOGLE_REFRESH_TOKEN | your_refresh_token    |
| KAGGLE_USERNAME      | your_kaggle_username  |
| KAGGLE_KEY           | your_kaggle_api_key   |

---

## KAGGLE SETUP

1. Go to kaggle.com -> Settings -> API -> Create New Token
2. Copy username and key to GitHub Secrets
3. On Kaggle: Notebook -> Settings -> Accelerator: T4 GPU + Internet ON
4. Update kernel-metadata.json:
   "id": "YOUR_ACTUAL_USERNAME/png-library-generator"

---

## GOOGLE DRIVE FOLDER (auto-created)

My Drive/
  png_library_images/
    food/indian/        <- Biryani, Dosa, Curry...
    food/world/         <- Pizza, Burger, Sushi...
    flowers/            <- Rose, Lotus, Jasmine...
    vehicles/cars/      <- Sports, SUV, Vintage...
    vehicles/bikes/     <- Royal Enfield, Sports...
    nature/trees/       <- Mango, Coconut, Oak...
    effects/smoke/      <- Smoke, Fire, Sparkle...
    sky_celestial/      <- Sun, Moon, Stars...
    cliparts/           <- Arrows, Hearts...
    frames_borders/     <- Wedding, Festival...
    offer_logos/        <- 50% OFF, BOGO, Sale...
    abstract/           <- Fluid, Geometric, Neon...
    furniture/          <- Chairs, Tables, Beds...
    tools/              <- Hand, Kitchen, Garden...
    festivals/          <- Diwali, Christmas, Eid...
    birds_insects/      <- Peacock, Butterfly...
    jewellery/          <- Necklace, Earrings...
    animals/            <- Farm, Wild, Sea, Pets...

---

## HOW TO RUN

Option 1 - Manual:
  GitHub -> Actions -> PNG Library Generator -> Run workflow
  start_index: 0, end_index: 1500

Option 2 - Auto Schedule:
  Runs every day at 2 AM IST (30 20 * * * UTC)
  1500 images/day -> 50,000 images in ~33 days
  Zero manual work needed!

---

## IMAGE SPECS

  Model       : FLUX.2 [klein] 4B (Apache 2.0)
  Gen size    : 2048 x 2048 px
  After upscale: 4096 x 4096 px (8K quality)
  Format      : PNG transparent (BRIA-RMBG-2.0)
  Steps       : 8 (quality optimised)
  CFG scale   : 3.5
  Uniqueness  : 46,502 unique prompts with random seeds

---

## TIME ESTIMATE

  FLUX.2 [klein] at 2048x2048 on T4  = ~15-20 sec/image
  Real-ESRGAN upscale 2048->4096      = ~5 sec/image
  BRIA-RMBG-2.0 background removal    = ~3 sec/image
  Total per image                     = ~25 sec

  1500 images/day x 33 days = ~50,000 images
  Cost = ZERO rupees!

---

## TROUBLESHOOTING

OOM error:
  Pipeline auto-retries at 1024x1024 if 2048x2048 OOMs
  Normal on first few batches -- model warms up

Upload failed:
  Check OAuth2 tokens -- refresh token should be permanent
  Re-run workflow with upload_only action

Kaggle kernel failed:
  Check kernel output on kaggle.com
  Ensure T4 GPU + Internet enabled in notebook settings

---

Happy PNG Generating! FLUX.2 Quality!
