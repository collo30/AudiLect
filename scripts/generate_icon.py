import os
import math
from PIL import Image, ImageDraw

def create_audilect_icon():
    size = 512
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Base rounded rectangle (squircle)
    margin = 24
    radius = 110
    
    # Create smooth gradient in a mask
    base_box = [margin, margin, size - margin, size - margin]
    
    # Draw background squircle
    draw.rounded_rectangle(base_box, radius=radius, fill=(24, 28, 48, 255))
    
    # Subtle inner gradient / accent border
    inner_box = [margin + 4, margin + 4, size - margin - 4, size - margin - 4]
    draw.rounded_rectangle(inner_box, radius=radius - 4, fill=(30, 41, 75, 255))
    
    # Draw top gradient highlight
    highlight_box = [margin + 8, margin + 8, size - margin - 8, size // 2]
    # Simple soft glow
    draw.rounded_rectangle([margin + 12, margin + 12, size - margin - 12, margin + 80], radius=40, fill=(49, 66, 120, 160))

    # 2. Modern audio-lecture waves & active intelligence spark
    # Draw 5 vertical rounded soundwave bars in the center
    # Heights: [100, 180, 260, 180, 100]
    bar_widths = 28
    bar_radius = 14
    center_x = size // 2
    center_y = size // 2
    
    heights = [110, 190, 270, 190, 110]
    spacing = 48
    start_x = center_x - (len(heights) - 1) * spacing // 2

    # Color palette: cyan-blue gradient look
    colors = [
        (96, 165, 250, 255),   # #60a5fa
        (56, 189, 248, 255),   # #38bdf8
        (255, 255, 255, 255),  # Pure white center
        (56, 189, 248, 255),   # #38bdf8
        (96, 165, 250, 255),   # #60a5fa
    ]

    for i, h in enumerate(heights):
        bx = start_x + i * spacing
        by1 = center_y - h // 2
        by2 = center_y + h // 2
        bar_box = [bx - bar_widths // 2, by1, bx + bar_widths // 2, by2]
        draw.rounded_rectangle(bar_box, radius=bar_radius, fill=colors[i])

    # 3. Add clean subtle horizontal timeline guide across bottom of waveform
    guide_y = center_y + 160
    guide_w = 260
    draw.rounded_rectangle(
        [center_x - guide_w // 2, guide_y - 3, center_x + guide_w // 2, guide_y + 3],
        radius=3,
        fill=(147, 197, 253, 140)
    )
    
    # Accent dot on timeline
    draw.ellipse([center_x - 7, guide_y - 7, center_x + 7, guide_y + 7], fill=(255, 255, 255, 255))

    # Resize to 256 for master icon
    master = img.resize((256, 256), Image.Resampling.LANCZOS)
    
    # Ensure directories exist
    os.makedirs("audilect/server/static", exist_ok=True)

    # Save master PNG
    master.save("audilect/server/static/icon.png", format="PNG")
    master.save("icon.png", format="PNG")

    # Generate multi-res ICO
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    master.save("icon.ico", format="ICO", sizes=sizes)
    master.save("audilect/server/static/favicon.ico", format="ICO", sizes=sizes)
    print("[+] Generated icon.png and icon.ico successfully!")

if __name__ == "__main__":
    create_audilect_icon()
