from PIL import Image

img = Image.open("Designer.png").convert("RGBA")
img.save(
    "arena_duel.ico",
    format="ICO",
    sizes=[(16,16), (32,32), (48,48), (64,64), (128,128), (256,256)]
)