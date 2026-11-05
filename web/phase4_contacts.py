from pathlib import Path
from PIL import Image, ImageDraw

folder=Path(__file__).parent/'docs/screenshots/phase4'
names=['dashboard','ecg','beat_selected','comparison','playback','ai_detection','experiment_nsvf','generalization','gallery','error_cases','presentation']
for resolution in ['1366x768','1440x900','1920x1080']:
    sheet=Image.new('RGB',(1600,1500),'#e4ecf5')
    draw=ImageDraw.Draw(sheet)
    for i,name in enumerate(names):
        path=folder/f'{name}_{resolution}.png'
        if not path.exists():
            continue
        image=Image.open(path).convert('RGB')
        crop=image.crop((0,0,image.width,min(image.height,image.width*.85)))
        crop.thumbnail((520,470))
        x=i%3*533+5
        y=i//3*375+25
        crop.thumbnail((520,345))
        sheet.paste(crop,(x,y))
        draw.text((x,y-20),f'{name} / {resolution}',fill='#182b49')
    sheet.save(folder/f'contact_{resolution}.png')
print('Contact sheets saved from actual screenshots; originals unchanged.')
