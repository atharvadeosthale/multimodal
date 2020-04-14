"""
Creative Common 4.0 License for reuse with citation
&copy; 2020 Stefano Pio Zingaro
"""

from __future__ import division, print_function

import fasttext
import numpy as np
import os
import random
import torch
import torch.nn.functional as F
from tqdm import tqdm
from PIL import Image, UnidentifiedImageError
from torch.backends import cudnn
from warnings import filterwarnings

filterwarnings("ignore")
cudnn.deterministic = True
cudnn.benchmark = False

torch.manual_seed(42)
np.random.seed(42)
random.seed(42)


def load_txt_samples(txt_data_dir):
    nlp = fasttext.load_model('/home/stefanopio.zingaro/Developer/multimodal-side-tuning/data/cc.en.300.bin')
    orig_dir = f'/data01/stefanopio.zingaro/datasets/{txt_data_dir}'
    save_dir = f'/home/stefanopio.zingaro/Developer/multimodal-side-tuning/data/{txt_data_dir}'
    for label in sorted(os.listdir(orig_dir)):
        class_path = f'{orig_dir}/{label}'
        with os.scandir(class_path) as it:
            for _, path in tqdm(enumerate(it)):
                with open(path, 'rb') as f:
                    txt = f.read()
                doc = [''.join([i for i in token.decode('UTF-8') if i.isalnum()]) for token in txt.split()]
                word2vec = [nlp[i] for i in doc]
                padding = 500 - len(word2vec)
                if padding > 0:
                    if padding == 500:
                        x = torch.zeros((500, 300))
                    else:
                        x = F.pad(torch.tensor(word2vec), [0, 0, 0, padding])
                else:
                    x = torch.tensor(word2vec[:500])

                if not os.path.exists(f'{save_dir}/{label}'):
                    os.mkdir(f'{save_dir}/{label}')
                torch.save(x.half(), f'{save_dir}/{label}/{"".join(path.name.split(".")[:-1])}.ptr')


def load_img_samples(img_data_dir):
    orig_dir = f'/data01/stefanopio.zingaro/datasets/{img_data_dir}'
    save_dir = f'/home/stefanopio.zingaro/Developer/multimodal-side-tuning/data/{img_data_dir}'
    for label in sorted(os.listdir(orig_dir)):
        class_path = f'{orig_dir}/{label}'
        with os.scandir(class_path) as it:
            for _, path in tqdm(enumerate(it)):
                with open(path, 'rb') as f:
                    try:
                        img = Image.open(f)
                        img = img.convert('RGB')
                        img = img.resize((384, 384))
                        if not os.path.exists(f'{save_dir}/{label}'):
                            os.mkdir(f'{save_dir}/{label}')
                        img.save(f'{save_dir}/{label}/{"".join(path.name.split(".")[:-1])}.jpg', "JPEG", quality=100)
                    except UnidentifiedImageError:
                        pass


if __name__ == '__main__':
    load_img_samples('Tobacco3482-jpg')
    load_txt_samples('QS-OCR-small')
    for s in ['val', 'test', 'train']:
        load_img_samples(f'RVL-CDIP/{s}')
        load_txt_samples(f'QS-OCR-Large/{s}')
