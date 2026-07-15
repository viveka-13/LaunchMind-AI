import os
import requests
import urllib.request
import uuid

PEXELS_BASE_URL = "https://api.pexels.com/v1/search"


def _get_query_from_idea(idea: str) -> str:
    """
    Derives a business-specific Pexels search query from the user's startup idea.
    Strips generic filler words so the query targets the actual business niche.
    Example: "AI-powered mental health app for teenagers" → "mental health teenagers"
    Example: "smart coffee shop loyalty platform"        → "coffee shop loyalty"
    """
    import re
    # Generic filler words that produce irrelevant stock photos
    STRIP_WORDS = {
        "ai", "app", "application", "platform", "system", "software", "tool",
        "startup", "business", "smart", "powered", "based", "using", "for",
        "the", "a", "an", "of", "and", "with", "in", "on", "to", "by",
        "automated", "autonomous", "intelligent", "digital", "online",
        "machine", "learning", "deep", "model", "saas", "web", "mobile",
        "solution", "service", "services", "management", "generator",
    }
    # Clean: lowercase, remove punctuation, split
    words = re.sub(r"[^a-zA-Z0-9\s]", " ", idea.lower()).split()
    meaningful = [w for w in words if w not in STRIP_WORDS and len(w) > 1]

    if len(meaningful) >= 2:
        # Take up to the first 4 meaningful words for a focused query
        return " ".join(meaningful[:4])
    elif meaningful:
        return meaningful[0]
    # Ultimate fallback — use the raw idea trimmed
    return idea.strip()[:40]


def fetch_images_for_startup(idea: str, num_images: int = 3) -> list:
    """
    Fetches contextually relevant images from Pexels API based on the startup idea.
    Returns a list of local file paths where images have been downloaded.
    """
    PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")  # read lazily so dotenv is loaded first
    image_paths = []
    images_dir = "./data/images"
    os.makedirs(images_dir, exist_ok=True)

    query = _get_query_from_idea(idea)

    if not PEXELS_API_KEY:
        print("[ImageService] PEXELS_API_KEY not set — skipping image fetch.")
        return []

    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": query, "per_page": num_images, "orientation": "landscape"}

    try:
        response = requests.get(PEXELS_BASE_URL, headers=headers, params=params, timeout=15)
        response.raise_for_status()
        photos = response.json().get("photos", [])

        for photo in photos:
            img_url = photo["src"]["large"]
            file_path = os.path.join(images_dir, f"{uuid.uuid4()}.jpg")
            img_response = requests.get(img_url, timeout=15, stream=True)
            img_response.raise_for_status()
            with open(file_path, "wb") as f:
                for chunk in img_response.iter_content(chunk_size=8192):
                    f.write(chunk)
            image_paths.append(file_path)

        print(f"[ImageService] Fetched {len(image_paths)} images from Pexels for query: '{query}'")

    except Exception as e:
        print(f"[ImageService] Pexels API error: {e}")

    return image_paths

def generate_flowchart(plan_id: str) -> str:
    """
    Generates a system architecture flowchart via mermaid.ink API.
    Returns the local path of the downloaded flowchart image, or None on failure.
    """
    import base64
    images_dir = "./data/images"
    os.makedirs(images_dir, exist_ok=True)

    # Generic but professional startup system workflow blueprint
    graph = (
        "graph TD\n"
        "    A[User Platform] -->|Inputs Data| B(API Gateway)\n"
        "    B --> C{Core Engine}\n"
        "    C -->|Reads/Writes| D[(Database)]\n"
        "    C --> E[AI/ML Models]\n"
        "    E -->|Predictions| C\n"
        "    C -->|Results| B\n"
        "    B -->|Displays UI| A\n"
        "    style A fill:#4f46e5,stroke:#fff,stroke-width:2px,color:#fff\n"
        "    style B fill:#10b981,stroke:#fff,stroke-width:2px,color:#fff\n"
        "    style C fill:#f59e0b,stroke:#fff,stroke-width:2px,color:#fff\n"
        "    style D fill:#a855f7,stroke:#fff,stroke-width:2px,color:#fff\n"
        "    style E fill:#f43f5e,stroke:#fff,stroke-width:2px,color:#fff\n"
    )

    base64_string = base64.b64encode(graph.encode("ascii")).decode("ascii")
    url = f"https://mermaid.ink/img/{base64_string}"

    file_path = os.path.join(images_dir, f"flowchart_{plan_id}.jpg")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as response, open(file_path, "wb") as out_file:
            out_file.write(response.read())
        print(f"[ImageService] Flowchart generated: {file_path}")
        return file_path
    except Exception as e:
        print(f"[ImageService] Flowchart generation failed: {e}")
        return None
