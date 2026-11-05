"""Contact sheets for manual review of the actual browser captures."""
from pathlib import Path
from PIL import Image, ImageDraw

folder=Path(__file__).parent/'docs/screenshots/phase3'
names=['dashboard','ai-detection','comparison','experiments','experiments_nsvf','generalization','gallery']
for size in ['1366x768','1440x900','1920x1080']:
    sheet=Image.new('RGB',(1500,1320),'#E5EAF1')
    draw=ImageDraw.Draw(sheet)
    for i,name in enumerate(names):
        source=Image.open(folder/f'{name}_{size}.png').convert('RGB')
        # Review the first 1000px at a common width; originals remain unmodified.
        crop=source.crop((0,0,source.width,min(source.height,source.width*0.8)))
        crop.thumbnail((490,400))
        x=(i%3)*500+5;y=(i//3)*440+28
        sheet.paste(crop,(x,y))
        draw.text((x,y-22),f'{name} / {size}',fill='#142B49')
    sheet.save(folder/f'contact_{size}.png')
print('Saved three manual-review contact sheets; source screenshots unchanged.')
