"""
    Multimodal side-tuning for document classification
    Copyright (C) 2020  S.P. Zingaro <mailto:stefanopio.zingaro@unibo.it>.

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

from __future__ import division, print_function

import random
from warnings import filterwarnings

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision
from torch.backends import cudnn

from .utils import merge

filterwarnings("ignore")
cudnn.deterministic = True
cudnn.benchmark = False

torch.manual_seed(42)
np.random.seed(42)
random.seed(42)


class FusionSideNetFcMobileNet(nn.Module):
    def __init__(self, embedding_dim, num_classes, alphas=None,
                 dropout_prob=.5, custom_embedding=False,
                 custom_num_embeddings=0, side_fc=512):
        super(FusionSideNetFcMobileNet, self).__init__()
        self.name = f'fusion-mobilenetv2-{side_fc}'
        if alphas is None:
            alphas = [.3, .3, .4]
        self.alphas = alphas

        self.base = MobileNet(num_classes=num_classes, classify=False)
        for param in self.base.parameters():
            param.requires_grad_(False)
        self.side_image = MobileNet(num_classes=num_classes, classify=False)
        self.image_output_dim = 1280
        self.side_text = ShawnNet(num_filters=512,
                                  windows=[3, 4, 5],
                                  num_classes=num_classes,
                                  dropout_prob=dropout_prob,
                                  classify=False)

        self.fc1fus = nn.Linear(self.side_text.num_filters * len(self.side_text.windows), self.image_output_dim)
        self.classifier = nn.Sequential(nn.Dropout(dropout_prob),
                                        nn.Linear(self.image_output_dim, side_fc),
                                        nn.Dropout(dropout_prob),
                                        nn.Linear(side_fc, num_classes))

    def forward(self, y):
        b_x, s_text_x = y

        s_image_x = b_x.clone()
        s_image_x = self.side_image(s_image_x)

        b_x = self.base(b_x)

        s_text_x = self.side_text(s_text_x)
        s_text_x = self.fc1fus(s_text_x)

        x, d = merge([b_x, s_image_x, s_text_x], self.alphas, return_distance=True)
        x = self.classifier(x)

        return x, d


class FusionSideNetFcResNet(nn.Module):
    def __init__(self, embedding_dim, num_classes, alphas=None,
                 dropout_prob=.5, custom_embedding=False,
                 custom_num_embeddings=0, side_fc=512):
        super(FusionSideNetFcResNet, self).__init__()
        self.name = f'fusion-resnet-{side_fc}'
        if alphas is None:
            alphas = [.3, .3]
        self.alphas = alphas

        self.base = ResNet(num_classes=num_classes, classify=False)
        for param in self.base.parameters():
            param.requires_grad_(False)
        self.side_image = ResNet(num_classes=num_classes, classify=False)
        self.image_output_dim = 2048
        self.side_text = ShawnNet(num_filters=512,
                                  windows=[3, 4, 5],
                                  num_classes=num_classes,
                                  dropout_prob=dropout_prob,
                                  classify=False)

        self.fc1fus = nn.Linear(self.side_text.num_filters * len(self.side_text.windows), self.image_output_dim)
        self.classifier = nn.Sequential(nn.Dropout(dropout_prob),
                                        nn.Linear(self.image_output_dim, side_fc),
                                        nn.Dropout(dropout_prob),
                                        nn.Linear(side_fc, num_classes))

    def forward(self, y):
        b_x, s_text_x = y

        s_image_x = b_x.clone()
        s_image_x = self.side_image(s_image_x)

        b_x = self.base(b_x)

        s_text_x = self.side_text(s_text_x)
        s_text_x = self.fc1fus(s_text_x)

        x, d = merge([b_x, s_image_x, s_text_x], self.alphas, return_distance=True)
        x = self.classifier(x)

        return x, d


class FusionSideNetFcVGG(nn.Module):
    def __init__(self, num_classes, alphas=None, dropout_prob=.5, side_fc=512):
        super(FusionSideNetFcVGG, self).__init__()
        self.name = f'fusion-vgg-{side_fc}'
        if alphas is None:
            alphas = [.3, .3, .4]
        self.alphas = alphas

        self.base = VGG(num_classes=num_classes, classify=False)
        for param in self.base.parameters():
            param.requires_grad_(False)
        self.side_image = VGG(num_classes=num_classes, classify=False)
        self.image_output_dim = 4096
        self.side_text = ShawnNet(num_filters=512,
                                  windows=[3, 4, 5],
                                  num_classes=num_classes,
                                  dropout_prob=dropout_prob,
                                  classify=False)

        self.fc1fus = nn.Linear(self.side_text.num_filters * len(self.side_text.windows), self.image_output_dim)
        self.classifier = nn.Sequential(nn.Dropout(dropout_prob),
                                        nn.Linear(self.image_output_dim, side_fc),
                                        nn.Dropout(dropout_prob),
                                        nn.Linear(side_fc, num_classes))

    def forward(self, y):
        b_x, s_text_x = y

        s_image_x = b_x.clone()
        s_image_x = self.side_image(s_image_x)

        b_x = self.base(b_x)

        s_text_x = self.side_text(s_text_x)
        s_text_x = self.fc1fus(s_text_x)

        x, d = merge([b_x, s_image_x, s_text_x], self.alphas, return_distance=True)
        x = self.classifier(x)

        return x, d


class VGG(nn.Module):
    def __init__(self, num_classes, classify=True):
        super(VGG, self).__init__()
        self.model = torchvision.models.vgg16(pretrained=True)
        self.name = 'vgg'
        self.classify = classify
        self.preclassifier = nn.Sequential(
                nn.Linear(512 * 7 * 7, 4096),
                nn.ReLU(True),
                nn.Dropout(),
                nn.Linear(4096, 4096),
                nn.ReLU(True),
            )
        if self.classify:
            self.classifier = nn.Sequential(
                nn.Dropout(),
                nn.Linear(4096, num_classes),
            )

    def forward(self, x):
        x = self.model.features(x)
        x = self.model.avgpool(x)
        x = torch.flatten(x, 1)
        x = self.preclassifier(x)
        if self.classify:
            x = self.classifier(x)
        return x


class ResNet(nn.Module):
    def __init__(self, num_classes, classify=True):
        super(ResNet, self).__init__()
        self.model = torchvision.models.resnet50(pretrained=True)
        self.name = 'resnet'
        expansion = 4
        self.classify = classify
        if self.classify:
            self.classifier = nn.Linear(512 * expansion, num_classes)

    def forward(self, x):
        x = self.model.conv1(x)
        x = self.model.bn1(x)
        x = self.model.relu(x)
        x = self.model.maxpool(x)

        x = self.model.layer1(x)
        x = self.model.layer2(x)
        x = self.model.layer3(x)
        x = self.model.layer4(x)

        x = self.model.avgpool(x)
        x = torch.flatten(x, 1)

        if self.classify:
            x = self.classifier(x)

        return x


class MobileNet(nn.Module):
    def __init__(self, num_classes, dropout_prob=.2, classify=True):
        super(MobileNet, self).__init__()
        self.model = torchvision.models.mobilenet_v2(pretrained=True)
        self.name = 'mobilenet'
        self.classify = classify
        if self.classify:
            self.classifier = nn.Sequential(nn.Dropout(dropout_prob),
                                            nn.Linear(self.model.last_channel,
                                                      num_classes))

    def forward(self, x):
        x = self.model.features(x)
        x = x.mean([2, 3])
        if self.classify:
            x = self.classifier(x)

        return x


class ShawnNet(nn.Module):
    def __init__(self, num_filters, windows, num_classes, dropout_prob=0.5, classify=True):
        super(ShawnNet, self).__init__()
        self.num_filters = num_filters
        self.windows = windows
        self.num_classes = num_classes
        self.dropout_prob = dropout_prob
        self.classify = classify

        self.embedding = nn.Embedding(256, 300)  # ASCII embedding
        self.convs = nn.ModuleList([
            nn.Conv1d(300, num_filters, w) for w in windows
        ])

        self.dropout = nn.Dropout(dropout_prob)
        if self.classify:
            self.fc = nn.Linear(len(self.windows) * self.num_filters, self.num_classes)

    def forward(self, x):
        x = x.clamp(0, 255).long()  # Ensure input is in valid range
        x = self.embedding(x)
        x = x.permute(0, 2, 1)  # (batch, 300, seq_len)
        x = [F.relu(conv(x)).squeeze(2) for conv in self.convs]
        x = [F.max_pool1d(i, i.size(2)).squeeze(2) for i in x]
        x = torch.cat(x, 1)
        x = self.dropout(x)
        if self.classify:
            x = self.fc(x)
        return x