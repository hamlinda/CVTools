from PIL import Image

def create(path='e2e_test.jpg'):
    img = Image.new('RGB', (320, 240), color=(73, 109, 137))
    img.save(path, 'JPEG')

if __name__ == '__main__':
    create()
