"""Convert a title to an ASCII URL slug; JSON stdin in, JSON stdout out."""
import json
import re
import sys
import unicodedata

arguments = json.load(sys.stdin)
text = unicodedata.normalize("NFKD", arguments["text"])
ascii_text = text.encode("ascii", "ignore").decode("ascii").lower()
slug = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")
print(json.dumps({"slug": slug}))
