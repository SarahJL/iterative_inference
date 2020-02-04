import os
import numpy as np
import cPickle as pickle
import dill
import torch
from time import strftime

from cfg.config import arch

global log_path


def init_log(log_root, train_config):
    # load/create log directory, format: day_month_year_hour_minutes_seconds
    global log_path

    if train_config['resume_experiment'] != '' and train_config['resume_experiment'] is not None:
        if os.path.exists(os.path.join(log_root, train_config['resume_experiment'])):
            log_path = os.path.join(log_root, train_config['resume_experiment'])
            return log_path, train_config['resume_experiment']
        else:
            raise Exception('Experiment folder ' + train_config['resume_experiment'] + ' not found.')

    log_dir = strftime("%b_%d_%Y_%H_%M_%S") + '/'
    log_path = os.path.join(log_root, log_dir)
    os.makedirs(log_path)
    # os.system("rsync -au --include '*/' --include '*.py' --exclude '*' . " + log_path + "source")
    os.makedirs(os.path.join(log_path, 'metrics'))
    os.makedirs(os.path.join(log_path, 'visualizations'))
    os.makedirs(os.path.join(log_path, 'checkpoints'))
    return log_path, log_dir


def update_metric(file_name, value):
    if os.path.exists(file_name):
        metric = pickle.load(open(file_name, 'r'))
        metric.append(value)
        pickle.dump(metric, open(file_name, 'w'))
    else:
        pickle.dump([value], open(file_name, 'w'))


def log_train(func):
    """Wrapper to log train metrics."""
    global log_path

    def log_func(model, train_config, arch, data, epoch, optimizers):
        output_dict = func(model, train_config, arch, data, epoch, optimizers)
        update_metric(os.path.join(log_path, 'metrics', 'train_elbo.p'), (epoch, output_dict['avg_elbo']))
        update_metric(os.path.join(log_path, 'metrics', 'train_cond_log_like.p'), (epoch, output_dict['avg_cond_log_like']))
        for level in range(len(model.levels)):
            update_metric(os.path.join(log_path, 'metrics', 'train_kl_level_' + str(level) + '.p'), (epoch, output_dict['avg_kl'][level]))
        return output_dict

    return log_func


def log_vis(func):
    """Wrapper to log metrics and visualizations."""
    global log_path

    def log_func(model, train_config, arch, data_loader, epoch, vis=False, eval=False):
        output_dict = func(model, train_config, arch, data_loader, vis=vis, eval=eval)
        update_metric(os.path.join(log_path, 'metrics', 'val_elbo.p'), (epoch, np.mean(output_dict['total_elbo'][:, -1], axis=0)))
        update_metric(os.path.join(log_path, 'metrics', 'val_cond_log_like.p'), (epoch, np.mean(output_dict['total_cond_log_like'][:, -1], axis=0)))
        for level in range(len(model.levels)):
            update_metric(os.path.join(log_path, 'metrics', 'val_kl_level_' + str(level) + '.p'), (epoch, np.mean(output_dict['total_kl'][level][:, -1], axis=0)))

        if vis:
            epoch_path = os.path.join(log_path, 'visualizations', 'epoch_' + str(epoch))
            if not os.path.exists(epoch_path):
                os.makedirs(epoch_path)

            batch_size = train_config['batch_size']
            n_iterations = train_config['n_iterations']
            batch, labels = next(iter(data_loader))
            if epoch == train_config['display_iter']:
                # save the data on the first display iteration
                pickle.dump(batch.numpy(), open(os.path.join(log_path, 'visualizations', 'batch_data.p'), 'w'))
                pickle.dump(labels.numpy(), open(os.path.join(log_path, 'visualizations', 'batch_labels.p'), 'w'))
            data_shape = list(batch.size())[1:]

            pickle.dump(output_dict['total_elbo'][:batch_size], open(os.path.join(epoch_path, 'elbo.p'), 'w'))
            pickle.dump(output_dict['total_cond_log_like'][:batch_size], open(os.path.join(epoch_path, 'cond_log_like.p'), 'w'))
            for level in range(len(model.levels)):
                pickle.dump(output_dict['total_kl'][level][:batch_size], open(os.path.join(epoch_path, 'kl_level_' + str(level) + '.p'), 'w'))

            pickle.dump(output_dict['total_posterior'][:batch_size], open(os.path.join(epoch_path, 'posterior.p'), 'w'))
            pickle.dump(output_dict['total_prior'][:batch_size], open(os.path.join(epoch_path, 'prior.p'), 'w'))
            recon = output_dict['total_recon'][:batch_size, :].reshape([batch_size, n_iterations+1]+data_shape)
            pickle.dump(recon, open(os.path.join(epoch_path, 'reconstructions.p'), 'w'))

            samples = output_dict['samples'].reshape([batch_size]+data_shape)
            pickle.dump(samples, open(os.path.join(epoch_path, 'samples.p'), 'w'))

            if arch['n_latent'][0] == 2 and len(arch['n_latent']) == 1:
                pickle.dump(output_dict['optimization_surface'], open(os.path.join(epoch_path, 'optimization_surface.p'), 'w'))

        if eval:
            eval_epoch_path = os.path.join(log_path, 'metrics', 'epoch_' + str(epoch))
            if not os.path.exists(eval_epoch_path):
                os.makedirs(eval_epoch_path)
            pickle.dump(output_dict['total_log_like'], open(os.path.join(eval_epoch_path, 'total_log_like.p'), 'w'))

        return output_dict

    return log_func


def save_checkpoint(model, opt, epoch):
    global log_path
    torch.save(model, os.path.join(log_path, 'checkpoints', 'epoch_'+str(epoch)+'_model.ckpt'), pickle_module=dill)
    torch.save(tuple(opt), os.path.join(log_path, 'checkpoints', 'epoch_'+str(epoch)+'_opt.ckpt'))


def get_last_epoch():
    global log_path
    last_epoch = 0
    for r, d, f in os.walk(os.path.join(log_path, 'checkpoints')):
        for ckpt_file_name in f:
            if ckpt_file_name[0] == 'e':
                epoch = int(ckpt_file_name.split('_')[1])
                if epoch > last_epoch:
                    last_epoch = epoch
    return last_epoch


def load_opt_checkpoint(epoch=-1):
    if epoch == -1:
        epoch = get_last_epoch()
    enc_opt, dec_opt = torch.load(os.path.join(log_path, 'checkpoints', 'epoch_'+str(epoch)+'_opt.ckpt'))
    return enc_opt, dec_opt, epoch


def load_model_checkpoint(epoch=-1, cuda_device=0):
    if epoch == -1:
        epoch = get_last_epoch()
    return torch.load(os.path.join(log_path, 'checkpoints', 'epoch_'+str(epoch)+'_model.ckpt'),
                      map_location={'cuda:0': 'cuda:' + str(cuda_device), 'cuda:1': 'cuda:' + str(cuda_device),
                                    'cpu': 'cuda:' + str(cuda_device)})
