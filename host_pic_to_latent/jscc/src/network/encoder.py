import torch
import torch.nn as nn
import torch.nn.functional as F

from src import utils


class ResidualBlock(nn.Module):
    def __init__(self, in_channels, kernel_size=3, stride=1, activation='relu'):
        """
        input_dims: Dimension of input tensor (B,C,H,W)
        """
        super(ResidualBlock, self).__init__()

        self.activation = getattr(F, activation)
        norm_kwargs = dict(momentum=0.1, affine=True, track_running_stats=False)

        self.interlayer_norm = utils.InstanceNorm2D_wrap

        pad_size = int((kernel_size-1)/2)
        self.pad = nn.ReflectionPad2d(pad_size)
        self.conv1 = nn.Conv2d(in_channels, in_channels, kernel_size, stride=stride)
        self.conv2 = nn.Conv2d(in_channels, in_channels, kernel_size, stride=stride)
        self.norm1 = self.interlayer_norm(in_channels, **norm_kwargs)
        self.norm2 = self.interlayer_norm(in_channels, **norm_kwargs)

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


class Encoder(nn.Module):
    def __init__(self, image_dims, C=32, n_residual_blocks=5, activation='relu'):
        """
        Encoder with convolutional architecture
        Projects image x ([C_in,256,256]) into a feature map of size C x W/64 x H/64
        ========
        Arguments:
        image_dims:  Dimensions of input image, (C_in,H,W)
        C:           Bottleneck depth, controls bits-per-pixel
        """

        super(Encoder, self).__init__()
        kernel_dim = 3
        filters = (64, 128, 256, 512)
        self.n_residual_blocks = n_residual_blocks

        im_channels = image_dims[0]

        # Layer / normalization options
        cnn_kwargs = dict(stride=2, padding=0, padding_mode='reflect')
        norm_kwargs = dict(momentum=0.1, affine=True, track_running_stats=False)
        activation_d = dict(relu='ReLU', elu='ELU', leaky_relu='LeakyReLU')
        self.activation = getattr(nn, activation_d[activation])  # (leaky_relu, relu, elu)
        self.n_downsampling_layers = 3

        self.interlayer_norm = utils.InstanceNorm2D_wrap

        self.pre_pad = nn.ReflectionPad2d(3)
        self.asymmetric_pad = nn.ReflectionPad2d((0, 1, 1, 0))  # Slower than tensorflow?
        self.post_pad = nn.ReflectionPad2d(1)

        # (256,256) -> (256,256), with implicit padding
        self.conv_block_init = nn.Sequential(
            self.pre_pad,
            nn.Conv2d(im_channels, filters[0], kernel_size=(7, 7), stride=1),
            self.interlayer_norm(filters[0], **norm_kwargs),
            self.activation(),
        )

        self.af0 = utils.AF_Module(filters[0])

        # (256,256) -> (128,128)
        self.conv_block1 = nn.Sequential(
            self.asymmetric_pad,
            nn.Conv2d(filters[0], filters[1], kernel_dim, **cnn_kwargs),
            self.interlayer_norm(filters[1], **norm_kwargs),
            self.activation(),
        )

        self.af1 = utils.AF_Module(filters[1])

        # (128,128) -> (64,64)
        self.conv_block2 = nn.Sequential(
            self.asymmetric_pad,
            nn.Conv2d(filters[1], filters[2], kernel_dim, **cnn_kwargs),
            self.interlayer_norm(filters[2], **norm_kwargs),
            self.activation(),
        )

        self.af2 = utils.AF_Module(filters[2])

        # (64,64) -> (32,32)
        self.conv_block3 = nn.Sequential(
            self.asymmetric_pad,
            nn.Conv2d(filters[2], filters[3], kernel_dim, **cnn_kwargs),
            self.interlayer_norm(filters[3], **norm_kwargs),
            self.activation(),
        )

        self.af3 = utils.AF_Module(filters[3])

        for m in range(n_residual_blocks):
            resblock_m = ResidualBlock(filters[3], activation=activation)
            af_m = utils.AF_Module(filters[3])
            self.add_module(f'resblock_{str(m)}', resblock_m)
            self.add_module(f'af_{str(m)}', af_m)

        # Project to channel input
        # (32,32) -> (32,32)
        self.conv_block_out = nn.Sequential(
            self.post_pad,
            nn.Conv2d(filters[3], C, kernel_dim, stride=1),
        )

    def forward(self, x, snr=0):
        x = self.conv_block_init(x)
        x = self.af0(x, snr)
        x = self.conv_block1(x)
        x = self.af1(x, snr)
        x = self.conv_block2(x)
        x = self.af2(x, snr)
        x = self.conv_block3(x)
        x = self.af3(x, snr)

        head = x

        for m in range(self.n_residual_blocks):
            resblock_m = getattr(self, f'resblock_{str(m)}')
            if m == 0:
                x = resblock_m(head)
            else:
                x = resblock_m(x)
            af_m = getattr(self, f'af_{str(m)}')
            x = af_m(x, snr)

        x += head

        out = self.conv_block_out(x)
        return out


if __name__ == "__main__":
    B = 16
    C = 32
    img = torch.randn([B, 3, 256, 256])
    x_dims = img.size()
    E = Encoder(x_dims[1:], C=C)

    y = E(img)
    print(y.size())
