import torch
import torch.nn as nn
import numpy as np
import json
import os, time, datetime
import logging
import itertools
from torchvision.utils import save_image
import torch.nn.functional as F
from torch.nn import init

# 原始导入（训练用，编码不需要）:
# from src.model import Model
# from src.super_model import SuperModel
# from src.test_model import TestModel
# from default_config import ModelTypes, ModelModes



def calculate_scale_and_zero_point(tensor, qmin=0, qmax=255):

    min_val = torch.min(tensor).item()
    max_val = torch.max(tensor).item()
    scale = (max_val - min_val) / (qmax - qmin)
    zero_point = qmin - np.round(min_val / scale)
    return torch.tensor(scale), torch.tensor(zero_point)

def quantize(tensor, scale, zero_point, qmin=0, qmax=255):

    q_tensor = torch.round(tensor / scale + zero_point)
    return torch.clamp(q_tensor, qmin, qmax).to(torch.uint8)

def dequantize(q_tensor, scale, zero_point):

    return (q_tensor.float() - zero_point) * scale







class Struct:
    def __init__(self, **entries):
        self.__dict__.update(entries)


def makedirs(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)


def count_parameters(model):
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def InstanceNorm2D_wrap(input_channels, momentum=0.1, affine=True,
                        track_running_stats=False, **kwargs):
    """
    Wrapper around default Torch instancenorm
    """
    instance_norm_layer = nn.InstanceNorm2d(input_channels,
                                            momentum=momentum, affine=affine,
                                            track_running_stats=track_running_stats)
    return instance_norm_layer


def setup_generic_signature(args, special_info):
    time_signature = '{:%Y_%m_%d_%H_%M}'.format(datetime.datetime.now()).replace(':', '_')
    if args.name is not None:
        args.name = '{}_{}_{}_{}'.format(args.name, args.dataset, special_info, time_signature)
    else:
        args.name = '{}_{}_{}'.format(args.dataset, special_info, time_signature)

    print(args.name)
    args.snapshot = os.path.join(args.save, args.name)
    args.checkpoints_save = os.path.join(args.snapshot, 'checkpoints')
    args.figures_save = os.path.join(args.snapshot, 'figures')
    args.storage_save = os.path.join(args.snapshot, 'storage')
    args.tensorboard_runs = os.path.join(args.snapshot, 'tensorboard')
    args.test_save = os.path.join(args.snapshot, 'test')

    makedirs(args.snapshot)
    makedirs(args.checkpoints_save)
    makedirs(args.figures_save)
    makedirs(args.storage_save)
    makedirs(os.path.join(args.tensorboard_runs, 'train'))
    makedirs(os.path.join(args.tensorboard_runs, 'test'))
    makedirs(args.test_save)

    return args


def logger_setup(logpath, filepath, package_files=[]):
    formatter = logging.Formatter('%(asctime)s %(levelname)s - %(funcName)s: %(message)s',
                                  "%H:%M:%S")
    logger = logging.getLogger(__name__)
    logger.setLevel('INFO'.upper())

    stream = logging.StreamHandler()
    stream.setLevel('INFO'.upper())
    stream.setFormatter(formatter)
    logger.addHandler(stream)

    info_file_handler = logging.FileHandler(logpath, mode="a")
    info_file_handler.setLevel('INFO'.upper())
    info_file_handler.setFormatter(formatter)
    logger.addHandler(info_file_handler)

    logger.info(filepath)

    for f in package_files:
        logger.info(f)
        with open(f, "r") as package_f:
            logger.info(package_f.read())
    return logger


def log_summaries(writer, storage, step, use_discriminator=False):
    weighted_compression_scalars = ['weighted_compression_loss',
                                    'weighted_distortion',
                                    'weighted_perceptual']

    compression_scalars = ['distortion', 'perceptual']
    gan_scalars = ['disc_loss', 'gen_loss', 'weighted_gen_loss', 'D_gen', 'D_real']

    compression_loss_breakdown = dict(total_comp=storage['weighted_compression_loss'][-1],
                                      weighted_distortion=storage['weighted_distortion'][-1],
                                      weighted_perceptual=storage['weighted_perceptual'][-1])

    for scalar in weighted_compression_scalars:
        writer.add_scalar('weighted_compression/{}'.format(scalar), storage[scalar][-1], step)

    for scalar in compression_scalars:
        writer.add_scalar('compression/{}'.format(scalar), storage[scalar][-1], step)

    if use_discriminator is True:
        compression_loss_breakdown['weighted_gen_loss'] = storage['weighted_gen_loss'][-1]
        for scalar in gan_scalars:
            writer.add_scalar('GAN/{}'.format(scalar), storage[scalar][-1], step)

    # Breakdown overall loss
    writer.add_scalars('compression_loss_breakdown', compression_loss_breakdown, step)


def log(model, storage, epoch, idx, mean_epoch_loss, current_loss, best_loss, start_time, epoch_start_time,
        batch_size, header='[TRAIN]', logger=None, writer=None, **kwargs):
    improved = ''
    t0 = epoch_start_time

    if current_loss < best_loss:
        best_loss = current_loss
        improved = '[*]'

    storage['epoch'].append(epoch)
    storage['mean_compression_loss'].append(mean_epoch_loss)
    storage['time'].append(time.time())

    # Tensorboard
    if writer is not None:
        log_summaries(writer, storage, model.step_counter, use_discriminator=model.use_discriminator)

    if logger is not None:
        report_f = logger.info
    else:
        report_f = print

    report_f('================>>>')
    report_f(header)
    report_f('================>>>')
    if header == '[TRAIN]':
        report_f(model.args.snapshot)
        report_f("Epoch {} | Mean epoch comp. loss: {:.3f} | Current comp. loss: {:.3f} | "
                 "Rate: {} examples/s | Time: {:.1f} s | Improved: {}".format(epoch, mean_epoch_loss, current_loss,
                                                                              int(batch_size * idx / (
                                                                                  (time.time() - t0))),
                                                                              time.time() - start_time, improved))
    else:
        report_f("Epoch {} | Mean epoch comp. loss: {:.3f} | Current comp. loss: {:.3f} | Improved: {}".format(epoch,
                                                                                                               mean_epoch_loss,
                                                                                                               current_loss,
                                                                                                               improved))
    report_f('========>')
    report_f("Distortion:")
    report_f(
        "Weighted Distortion: {:.3f} | Weighted Perceptual: {:.3f} | Distortion: {:.3f}".format(
            storage['weighted_distortion'][-1],
            storage['weighted_perceptual'][-1],
            storage['distortion'][-1]))
    if model.use_discriminator is True:
        report_f('========>')
        report_f("Generator-Discriminator:")
        report_f("G Loss: {:.3f} | D Loss: {:.3f} | D(gen): {:.3f} | D(real): {:.3f}".format(storage['gen_loss'][-1],
                                                                                             storage['disc_loss'][-1],
                                                                                             storage['D_gen'][-1],
                                                                                             storage['D_real'][-1]))

    return best_loss


def log_summaries_super(writer, storage, step, use_discriminator=False):
    weighted_compression_scalars = ['weighted_compression_loss',
                                    'weighted_distortion',
                                    'weighted_perceptual',
                                    'weighted_distillation']

    compression_scalars = ['distortion', 'perceptual', 'distillation']
    gan_scalars = ['disc_loss', 'gen_loss', 'weighted_gen_loss', 'D_gen', 'D_real']

    compression_loss_breakdown = dict(total_comp=storage['weighted_compression_loss'][-1],
                                      weighted_distortion=storage['weighted_distortion'][-1],
                                      weighted_perceptual=storage['weighted_perceptual'][-1],
                                      weighted_distillation=storage['weighted_distillation'][-1])

    for scalar in weighted_compression_scalars:
        writer.add_scalar('weighted_compression/{}'.format(scalar), storage[scalar][-1], step)

    for scalar in compression_scalars:
        writer.add_scalar('compression/{}'.format(scalar), storage[scalar][-1], step)

    if use_discriminator is True:
        compression_loss_breakdown['weighted_gen_loss'] = storage['weighted_gen_loss'][-1]
        for scalar in gan_scalars:
            writer.add_scalar('GAN/{}'.format(scalar), storage[scalar][-1], step)

    # Breakdown overall loss
    writer.add_scalars('compression_loss_breakdown', compression_loss_breakdown, step)


def log_super(model, storage, epoch, idx, mean_epoch_loss, current_loss, best_loss, start_time, epoch_start_time,
              batch_size, header='[TRAIN]', logger=None, writer=None, **kwargs):
    improved = ''
    t0 = epoch_start_time

    if current_loss < best_loss:
        best_loss = current_loss
        improved = '[*]'

    storage['epoch'].append(epoch)
    storage['mean_compression_loss'].append(mean_epoch_loss)
    storage['time'].append(time.time())

    # Tensorboard
    if writer is not None:
        log_summaries_super(writer, storage, model.step_counter, use_discriminator=model.use_discriminator)

    if logger is not None:
        report_f = logger.info
    else:
        report_f = print

    report_f('================>>>')
    report_f(header)
    report_f('================>>>')
    if header == '[TRAIN]':
        report_f(model.args.snapshot)
        report_f("Epoch {} | Mean epoch comp. loss: {:.3f} | Current comp. loss: {:.3f} | "
                 "Rate: {} examples/s | Time: {:.1f} s | Improved: {}".format(epoch, mean_epoch_loss, current_loss,
                                                                              int(batch_size * idx / (
                                                                                  (time.time() - t0))),
                                                                              time.time() - start_time, improved))
    else:
        report_f("Epoch {} | Mean epoch comp. loss: {:.3f} | Current comp. loss: {:.3f} | Improved: {}".format(epoch,
                                                                                                               mean_epoch_loss,
                                                                                                               current_loss,
                                                                                                               improved))
    report_f('========>')
    report_f("Distortion:")
    report_f(
        "Weighted Distortion: {:.3f} | Weighted Perceptual: {:.3f} | Distortion: {:.3f}".format(
            storage['weighted_distortion'][-1],
            storage['weighted_perceptual'][-1],
            storage['distortion'][-1]))
    report_f('========>')
    report_f("Generator-Discriminator:")
    report_f("G Loss: {:.3f} | D Loss: {:.3f} | D(gen): {:.3f} | D(real): {:.3f}".format(storage['gen_loss'][-1],
                                                                                         storage['disc_loss'][-1],
                                                                                         storage['D_gen'][-1],
                                                                                         storage['D_real'][-1]))
    report_f('========>')
    report_f("Distillation:")
    report_f("Distillation: {:.3f} | Weighted Distillation: {:.3f}".format(storage['distillation'][-1],
                                                                           storage['weighted_distillation'][-1]))

    return best_loss


def save_model(model, optimizers, mean_epoch_loss, epoch, device, args, logger, multigpu=False):
    directory = args.checkpoints_save
    makedirs(directory)
    model.cpu()  # Move model parameters to CPU for consistency when restoring

    metadata = dict(image_dims=args.image_dims, epoch=epoch, steps=model.step_counter)
    args_d = dict((n, getattr(args, n)) for n in dir(args) if not (n.startswith('_') or 'logger' in n))
    metadata.update(args_d)
    timestamp = '{:%Y_%m_%d_%H_%M}'.format(datetime.datetime.now())
    args_d['timestamp'] = timestamp

    model_name = args.name
    metadata_path = os.path.join(directory, 'metadata/model_{}_metadata_{}.json'.format(model_name, timestamp))
    makedirs(os.path.join(directory, 'metadata'))

    if not os.path.isfile(metadata_path):
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=4, sort_keys=True)

    model_path = os.path.join(directory,
                              '{}_epoch{}_idx{}_{}.pt'.format(model_name, epoch, model.step_counter, timestamp))

    if os.path.exists(model_path):
        model_path = os.path.join(directory, '{}_epoch{}_idx{}_{:%Y_%m_%d_%H_%M_%S}.pt'.format(model_name, epoch,
                                                                                               model.step_counter,
                                                                                               datetime.datetime.now()))

    save_dict = {'model_state_dict': model.module.state_dict() if args.multi_gpu is True else model.state_dict(),
                 'compression_optimizer_state_dict': optimizers['amort'].state_dict(),
                 'epoch': epoch,
                 'steps': model.step_counter,
                 'args': args_d,
                 }

    torch.save(save_dict, f=model_path)
    logger.info('Saved model at Epoch {}, step {} to {}'.format(epoch, model.step_counter, model_path))

    model.to(device)  # Move back to device
    return model_path


def save_images(writer, step, real, decoded, fname):
    imgs = torch.cat((real, decoded), dim=0)
    save_image(imgs, fname, nrow=4, normalize=True, scale_each=True)
    writer.add_images('gen_recon', imgs, step)


def get_scheduled_params(param, param_schedule, step_counter, ignore_schedule=False):
    # e.g. schedule = dict(vals=[1., 0.1], steps=[N])
    # reduces param value by a factor of 0.1 after N steps
    if ignore_schedule is False:
        vals, steps = param_schedule['vals'], param_schedule['steps']
        assert (len(vals) == len(steps) + 1), f'Mispecified schedule! - {param_schedule}'
        idx = np.where(step_counter < np.array(steps + [step_counter + 1]))[0][0]
        param *= vals[idx]
    return param


def update_lr(args, optimizer, itr, logger):
    lr = get_scheduled_params(args.learning_rate, args.lr_schedule, itr)
    for param_group in optimizer.param_groups:
        old_lr = param_group['lr']
        if old_lr != lr:
            logger.info('=============================')
            logger.info(f'Changing learning rate {old_lr} -> {lr}')
            param_group['lr'] = lr


def load_model(save_path, logger, device, model_type=None, model_mode=None, current_args_d=None,
               strict=False, silent=False):
    start_time = time.time()
    checkpoint = torch.load(save_path, map_location=device)
    loaded_args_d = checkpoint['args']

    args = Struct(**loaded_args_d)

    if current_args_d is not None:
        if silent is False:
            for k, v in current_args_d.items():
                try:
                    loaded_v = loaded_args_d[k]
                except KeyError:
                    logger.warning(
                        'Argument {} (value {}) not present in recorded arguments. Using current argument.'.format(k,
                                                                                                                   v))
                    continue

                if loaded_v != v:
                    logger.warning(
                        'Current argument {} (value {}) does not match recorded argument (value {}). Recorded argument will be overriden.'.format(
                            k, v, loaded_v))

        # HACK
        loaded_args_d.update(current_args_d)
        args = Struct(**loaded_args_d)

    if model_type is None:
        model_type = args.model_type

    if model_mode is None:
        model_mode = args.model_mode

    model = Model(args, logger, model_type=model_type, model_mode=model_mode)

    # `strict` False if warmstarting
    model.load_state_dict(checkpoint['model_state_dict'], strict=strict)

    # logger.info('Loading model ...')
    # if silent is False:
    #     logger.info('MODEL TYPE: {}'.format(model_type))
    #     logger.info('MODEL MODE: {}'.format(model_mode))
    #     logger.info(model)
    #     logger.info('Trainable parameters:')
    #     for n, p in model.named_parameters():
    #         logger.info('{} - {}'.format(n, p.shape))
    #
    #     logger.info("Number of trainable parameters: {}".format(count_parameters(model)))
    # logger.info("Estimated model size (under fp32): {:.3f} MB".format(count_parameters(model) * 4. / 10 ** 6))
    # logger.info('Model init {:.3f}s'.format(time.time() - start_time))

    model = model.to(device)

    if model_mode == ModelModes.EVALUATION:
        model.eval()
        optimizers = None
    else:
        amortization_parameters = itertools.chain.from_iterable(
            [am.parameters() for am in model.amortization_models])
        amortization_opt = torch.optim.Adam(amortization_parameters,
                                            lr=args.learning_rate)
        optimizers = dict(amort=amortization_opt)

        if model.use_discriminator is True:
            discriminator_parameters = model.Discriminator.parameters()
            disc_opt = torch.optim.Adam(discriminator_parameters, lr=args.learning_rate)
            optimizers['disc'] = disc_opt

        model.train()

    return args, model, optimizers


def load_super_model(save_path, logger, device, model_type=None, model_mode=None, current_args_d=None,
                     strict=False, silent=False):
    start_time = time.time()
    checkpoint = torch.load(save_path, map_location=device)
    loaded_args_d = checkpoint['args']

    args = Struct(**loaded_args_d)

    if current_args_d is not None:
        if silent is False:
            for k, v in current_args_d.items():
                try:
                    loaded_v = loaded_args_d[k]
                except KeyError:
                    logger.warning(
                        'Argument {} (value {}) not present in recorded arguments. Using current argument.'.format(k,
                                                                                                                   v))
                    continue

                if loaded_v != v:
                    logger.warning(
                        'Current argument {} (value {}) does not match recorded argument (value {}). Recorded argument will be overriden.'.format(
                            k, v, loaded_v))

        # HACK
        loaded_args_d.update(current_args_d)
        args = Struct(**loaded_args_d)

    if model_type is None:
        model_type = args.model_type

    if model_mode is None:
        model_mode = args.model_mode

    model = SuperModel(args, logger, model_type=model_type, model_mode=model_mode)

    # `strict` False if warmstarting
    model.load_state_dict(checkpoint['model_state_dict'], strict=strict)

    # logger.info('Loading model ...')
    # if silent is False:
    #     logger.info('MODEL TYPE: {}'.format(model_type))
    #     logger.info('MODEL MODE: {}'.format(model_mode))
    #     logger.info(model)
    #     logger.info('Trainable parameters:')
    #     for n, p in model.named_parameters():
    #         logger.info('{} - {}'.format(n, p.shape))
    #
    # logger.info("Number of trainable parameters of encoder: {}".format(count_parameters(model.Encoder)))
    # logger.info(
    #     "Estimated size (under fp32): {:.3f} MB".format(count_parameters(model.Encoder) * 4. / 10 ** 6))
    # logger.info("Number of trainable parameters of generator: {}".format(count_parameters(model.Generator)))
    # logger.info(
    #     "Estimated size (under fp32): {:.3f} MB".format(count_parameters(model.Generator) * 4. / 10 ** 6))
    # logger.info("Number of trainable parameters: {}".format(count_parameters(model)))
    # logger.info("Estimated size (under fp32): {:.3f} MB".format(count_parameters(model) * 4. / 10 ** 6))
    # logger.info('Model init {:.3f}s'.format(time.time() - start_time))

    model = model.to(device)

    if model_mode == ModelModes.EVALUATION:
        model.eval()
        optimizers = None
    else:
        amortization_parameters = itertools.chain.from_iterable(
            [am.parameters() for am in model.amortization_models])
        amortization_opt = torch.optim.Adam(amortization_parameters,
                                            lr=args.learning_rate)
        optimizers = dict(amort=amortization_opt)

        if model.use_discriminator is True:
            discriminator_parameters = model.Discriminator.parameters()
            disc_opt = torch.optim.Adam(discriminator_parameters, lr=args.learning_rate)
            optimizers['disc'] = disc_opt

        model.train()

    return args, model, optimizers


def load_test_model(config_str, G_save_path, save_path, logger, device, model_type=None, model_mode=None, current_args_d=None,
                     strict=False, silent=False):
    start_time = time.time()
    checkpoint = torch.load(save_path, map_location=device)
    G_checkpoint = torch.load(G_save_path, map_location=device)
    loaded_args_d = checkpoint['args']

    args = Struct(**loaded_args_d)

    if current_args_d is not None:
        if silent is False:
            for k, v in current_args_d.items():
                try:
                    loaded_v = loaded_args_d[k]
                except KeyError:
                    logger.warning(
                        'Argument {} (value {}) not present in recorded arguments. Using current argument.'.format(k,
                                                                                                                   v))
                    continue

                if loaded_v != v:
                    logger.warning(
                        'Current argument {} (value {}) does not match recorded argument (value {}). Recorded argument will be overriden.'.format(
                            k, v, loaded_v))

        # HACK
        loaded_args_d.update(current_args_d)
        args = Struct(**loaded_args_d)

    if model_type is None:
        model_type = args.model_type

    if model_mode is None:
        model_mode = args.model_mode

    args.config_str = config_str

    model = TestModel(args, logger, model_type=model_type, model_mode=model_mode)

    # `strict` False if warmstarting
    model.load_state_dict(checkpoint['model_state_dict'], strict=strict)
    model.C_generator.load_state_dict(G_checkpoint, strict=strict)

    # logger.info('Loading model ...')
    # if silent is False:
    #     logger.info('MODEL TYPE: {}'.format(model_type))
    #     logger.info('MODEL MODE: {}'.format(model_mode))
    #     logger.info(model)
    #     logger.info('Trainable parameters:')
    #     for n, p in model.named_parameters():
    #         logger.info('{} - {}'.format(n, p.shape))
    #
    # logger.info("Number of trainable parameters of encoder: {}".format(count_parameters(model.Encoder)))
    # logger.info(
    #     "Estimated size (under fp32): {:.3f} MB".format(count_parameters(model.Encoder) * 4. / 10 ** 6))
    # logger.info("Number of trainable parameters of generator: {}".format(count_parameters(model.C_generator)))
    # logger.info(
    #     "Estimated size (under fp32): {:.3f} MB".format(count_parameters(model.C_generator) * 4. / 10 ** 6))
    # logger.info("Number of trainable parameters: {}".format(count_parameters(model)))
    # logger.info("Estimated size (under fp32): {:.3f} MB".format(count_parameters(model) * 4. / 10 ** 6))
    # logger.info('Model init {:.3f}s'.format(time.time() - start_time))

    model = model.to(device)

    model.eval()

    return args, model


def psnr_fn(img1, img2, max_val=255.):
    """
    Based on `tf.image.psnr`
    https://www.tensorflow.org/api_docs/python/tf/image/psnr
    """
    float_type = 'float64'

    img1 = img1.astype(float_type)
    img2 = img2.astype(float_type)
    mse = np.mean(np.square(img1 - img2), axis=(1, 2, 3))
    psnr = 20 * np.log10(max_val) - 10 * np.log10(mse)
    return psnr


def pad_factor(input_image, spatial_dims, factor):
    """Pad `input_image` (N,C,H,W) such that H and W are divisible by `factor`."""

    if isinstance(factor, int) is True:
        factor_H = factor
        factor_W = factor_H
    else:
        factor_H, factor_W = factor

    H, W = spatial_dims[0], spatial_dims[1]
    pad_H = (factor_H - (H % factor_H)) % factor_H
    pad_W = (factor_W - (W % factor_W)) % factor_W
    return F.pad(input_image, pad=(0, pad_W, 0, pad_H), mode='reflect')


def _non_saturating_loss(D_real_logits, D_gen_logits, D_real=None, D_gen=None):
    D_loss_real = F.binary_cross_entropy_with_logits(input=D_real_logits,
                                                     target=torch.ones_like(D_real_logits))
    D_loss_gen = F.binary_cross_entropy_with_logits(input=D_gen_logits,
                                                    target=torch.zeros_like(D_gen_logits))
    D_loss = D_loss_real + D_loss_gen

    G_loss = F.binary_cross_entropy_with_logits(input=D_gen_logits,
                                                target=torch.ones_like(D_gen_logits))

    return D_loss, G_loss


def _least_squares_loss(D_real, D_gen, D_real_logits=None, D_gen_logits=None):
    D_loss_real = torch.mean(torch.square(D_real - 1.0))
    D_loss_gen = torch.mean(torch.square(D_gen))
    D_loss = 0.5 * (D_loss_real + D_loss_gen)

    G_loss = 0.5 * torch.mean(torch.square(D_gen - 1.0))

    return D_loss, G_loss


def gan_loss(gan_loss_type, disc_out, mode='generator_loss'):
    if gan_loss_type == 'non_saturating':
        loss_fn = _non_saturating_loss
    elif gan_loss_type == 'least_squares':
        loss_fn = _least_squares_loss
    else:
        raise ValueError('Invalid GAN loss')

    D_loss, G_loss = loss_fn(D_real=disc_out.D_real, D_gen=disc_out.D_gen,
                             D_real_logits=disc_out.D_real_logits, D_gen_logits=disc_out.D_gen_logits)

    loss = G_loss if mode == 'generator_loss' else D_loss

    return loss


def init_weights(net, init_type='normal', init_gain=0.02):
    """Initialize network weights.

    Parameters:
        net (network)   -- network to be initialized
        init_type (str) -- the name of an initialization method: normal | xavier | kaiming | orthogonal
        init_gain (float)    -- scaling factor for normal, xavier and orthogonal.

    We use 'normal' in the original pix2pix and CycleGAN paper. But xavier and kaiming might
    work better for some applications. Feel free to try yourself.
    """

    def init_func(m):  # define the initialization function
        classname = m.__class__.__name__
        if hasattr(m, 'weight') and (classname.find('Conv') != -1 or classname.find('Linear') != -1):
            if init_type == 'normal':
                init.normal_(m.weight.data, 0.0, init_gain)
            elif init_type == 'xavier':
                init.xavier_normal_(m.weight.data, gain=init_gain)
            elif init_type == 'kaiming':
                init.kaiming_normal_(m.weight.data, a=0, mode='fan_in')
            elif init_type == 'orthogonal':
                init.orthogonal_(m.weight.data, gain=init_gain)
            else:
                raise NotImplementedError('initialization method [%s] is not implemented' % init_type)
            if hasattr(m, 'bias') and m.bias is not None:
                init.constant_(m.bias.data, 0.0)
        elif classname.find(
                'BatchNorm2d') != -1:  # BatchNorm Layer's weight is not a matrix; only normal distribution applies.
            if hasattr(m, 'weight') and m.weight is not None:
                init.normal_(m.weight.data, 1.0, init_gain)
            if hasattr(m, 'bias') and m.weight is not None:
                init.constant_(m.bias.data, 0.0)

    print('initialize network with %s' % init_type)
    net.apply(init_func)  # apply the initialization function <init_func>


def init_net(net, init_type='normal', init_gain=0.02, gpu_ids=[]):
    """Initialize a network: 1. register CPU/GPU device (with multi-GPU support); 2. initialize the network weights
    Parameters:
        net (network)      -- the network to be initialized
        init_type (str)    -- the name of an initialization method: normal | xavier | kaiming | orthogonal
        gain (float)       -- scaling factor for normal, xavier and orthogonal.
        gpu_ids (int list) -- which GPUs the network runs on: e.g., 0,1,2

    Return an initialized network.
    """
    if len(gpu_ids) > 0:
        assert (torch.cuda.is_available())
        net.to(gpu_ids[0])
        if len(gpu_ids) > 1:
            net = torch.nn.DataParallel(net, gpu_ids)  # multi-GPUs
    init_weights(net, init_type, init_gain=init_gain)

    return net


class AF_Module(nn.Module):
    def __init__(self, ch_num):
        super(AF_Module, self).__init__()
        self.global_avg_pool = nn.AdaptiveAvgPool2d((1, 1))
        self.dense1 = nn.Linear(ch_num + 1, ch_num // 16)
        self.dense2 = nn.Linear(ch_num // 16, ch_num)
        self.ch_num = ch_num

    def forward(self, x, snr):
        m = self.global_avg_pool(x)
        m = m.view(-1, self.ch_num)

        if isinstance(snr, (int, float)):
            snr = torch.tensor([snr], dtype=torch.float32, device=x.device).unsqueeze(0)
            snr = snr.expand(x.size(0), -1)

        m = torch.cat((m, snr), dim=1)

        m = F.relu(self.dense1(m))
        m = torch.sigmoid(self.dense2(m))

        m = m.view(-1, self.ch_num, 1, 1)

        out = x * m
        return out
