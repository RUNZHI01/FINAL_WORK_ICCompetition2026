import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np

# Custom
from src.network.super_modules import SuperConvTranspose2d, SuperConv2d, SuperSeparableConv2d, SeparableConv2d


class SubMobileResidualBlock(nn.Module):
    def __init__(self, ic, oc, kernel_size=3, stride=1, activation='relu'):
        """
        input_dims: Dimension of input tensor (B,C,H,W)
        """
        super(SubMobileResidualBlock, self).__init__()

        self.activation = getattr(F, activation)

        self.interlayer_norm = nn.InstanceNorm2d

        pad_size = int((kernel_size - 1) / 2)
        self.pad = nn.ReflectionPad2d(pad_size)
        self.conv1 = SeparableConv2d(in_channels=ic, out_channels=oc, kernel_size=kernel_size, stride=stride)
        self.conv2 = SeparableConv2d(in_channels=oc, out_channels=ic, kernel_size=kernel_size, stride=stride)
        self.norm1 = self.interlayer_norm(oc)
        self.norm2 = self.interlayer_norm(ic)

    def forward(self, x):
        identity_map = x
        res = self.pad(x)
        res = self.conv1(res)
        res = self.norm1(res)
        res = self.activation(res)

        res = self.pad(res)
        res = self.conv2(res)
        res = self.norm2(res)

        return torch.add(res, identity_map)


class SubMobileGenerator(nn.Module):
    def __init__(self, image_dims, config, C=32, n_residual_blocks=5, activation='relu'):

        super(SubMobileGenerator, self).__init__()

        kernel_dim = 3
        self.n_residual_blocks = n_residual_blocks

        # Layer / normalization options
        cnn_kwargs = dict(stride=2, padding=1, output_padding=1)
        norm_kwargs = dict(momentum=0.1, affine=True, track_running_stats=False)
        activation_d = dict(relu='ReLU', elu='ELU', leaky_relu='LeakyReLU')
        self.activation = getattr(nn, activation_d[activation])  # (leaky_relu, relu, elu)
        self.n_upsampling_layers = 3

        self.interlayer_norm = nn.InstanceNorm2d

        self.pre_pad = nn.ReflectionPad2d(1)
        self.asymmetric_pad = nn.ReflectionPad2d((0, 1, 1, 0))  # Slower than tensorflow?
        self.post_pad = nn.ReflectionPad2d(3)

        ##############################
        # (32,32) -> (32,32), with implicit padding
        # self.conv_block_init = nn.Sequential(
        #     self.interlayer_norm(C, **norm_kwargs),
        #     self.pre_pad,
        #     SuperConv2d(C, filters[0], kernel_size=(3,3), stride=1),
        #     self.interlayer_norm(filters[0], **norm_kwargs),
        # )
        self.interlayer_norm01 = self.interlayer_norm(C)
        self.pre_pad01 = self.pre_pad
        aaa=config['channels']
        self.conv01 = nn.Conv2d(C, config['channels'][0] * 16, kernel_size=(3, 3), stride=1)
        self.interlayer_norm02 = self.interlayer_norm(config['channels'][0] * 16)
        ##############################

        ic = config['channels'][0] * 16
        for m in range(n_residual_blocks):
            oc = config['channels'][1 + int(m / 3)] * 16
            resblock_m = SubMobileResidualBlock(ic, oc, activation=activation)
            self.add_module(f'resblock_{str(m)}', resblock_m)

        ##############################
        # (32,32) -> (64,64)
        # self.upconv_block1 = nn.Sequential(
        #     SuperConvTranspose2d(filters[0], filters[1], kernel_dim, **cnn_kwargs),
        #     self.interlayer_norm(filters[1], **norm_kwargs),
        #     self.activation(),
        # )
        self.convt1 = nn.ConvTranspose2d(config['channels'][0] * 16, config['channels'][3] * 8, kernel_dim, **cnn_kwargs)
        self.interlayer_norm1 = self.interlayer_norm(config['channels'][3] * 8)
        self.act1 = self.activation()
        ##############################

        ##############################
        # self.upconv_block2 = nn.Sequential(
        #     SuperConvTranspose2d(filters[1], filters[2], kernel_dim, **cnn_kwargs),
        #     self.interlayer_norm(filters[2], **norm_kwargs),
        #     self.activation(),
        # )
        self.convt2 = nn.ConvTranspose2d(config['channels'][3] * 8, config['channels'][4] * 4, kernel_dim, **cnn_kwargs)
        self.interlayer_norm2 = self.interlayer_norm(config['channels'][4] * 4)
        self.act2 = self.activation()
        ##############################

        ##############################
        # self.upconv_block3 = nn.Sequential(
        #     SuperConvTranspose2d(filters[2], filters[3], kernel_dim, **cnn_kwargs),
        #     self.interlayer_norm(filters[3], **norm_kwargs),
        #     self.activation(),
        # )
        self.convt3 = nn.ConvTranspose2d(config['channels'][4] * 4, config['channels'][5] * 2, kernel_dim, **cnn_kwargs)
        self.interlayer_norm3 = self.interlayer_norm(config['channels'][5] * 2)
        self.act3 = self.activation()
        ##############################

        ##############################
        # self.conv_block_out = nn.Sequential(
        #     self.post_pad,
        #     SuperConv2d(filters[-1], 3, kernel_size=(7, 7), stride=1),
        # )
        self.post_pad11 = self.post_pad
        self.conv11 = nn.Conv2d(config['channels'][5] * 2, 3, kernel_size=(7, 7), stride=1)
        ##############################

    def forward(self, x):

        ##############################
        # head = self.conv_block_init(x)
        head = self.interlayer_norm01(x)
        head = self.pre_pad01(head)
        head = self.conv01(head)
        head = self.interlayer_norm02(head)
        ##############################

        ##############################
        # for m in range(self.n_residual_blocks):
        #     resblock_m = getattr(self, f'resblock_{str(m)}')
        #     if m == 0:
        #         x = resblock_m(head)
        #     else:
        #         x = resblock_m(x)
        for m in range(self.n_residual_blocks):
            resblock_m = getattr(self, f'resblock_{str(m)}')
            if m == 0:
                x = resblock_m(head)
            else:
                x = resblock_m(x)  # 1 config for 3 block
        ##############################

        x += head

        ##############################
        # x = self.upconv_block1(x)
        # x = self.upconv_block2(x)
        # x = self.upconv_block3(x)
        # x = self.upconv_block4(x)
        x = self.convt1(x)
        x = self.interlayer_norm1(x)
        x = self.act1(x)

        x = self.convt2(x)
        x = self.interlayer_norm2(x)
        x = self.act2(x)

        x = self.convt3(x)
        x = self.interlayer_norm3(x)
        x = self.act3(x)
        ##############################

        ##############################
        # out = self.conv_block_out(x)
        x = self.post_pad11(x)
        out = self.conv11(x)
        ##############################

        return out
