from config import train_config, arch
from models import LatentVariableModel
from util.data import load_data
from util.misc import get_optimizers
from util.train_val import run
from util.plotting import initialize_env, initialize_plots, save_env
import time

# todo: set up logging
# todo: better visualization

global vis
vis = initialize_env('test')
handle_dict = initialize_plots()

data_path = '/home/joe/Datasets'

# data, labels
(train_data, train_labels), (val_data, val_labels) = load_data(train_config['dataset'], data_path)

# construct model
model = LatentVariableModel(train_config, arch, train_data.shape[1:])

# get optimizers
(enc_opt, enc_sched), (dec_opt, dec_sched) = get_optimizers(train_config, model)

for epoch in range(10000):
    tic = time.time()
    # train
    train(model, train_config, train_data, (enc_opt, dec_opt), epoch+1, handle_dict)
    toc = time.time()
    print 'Time: ' + str(toc - tic)
    print train_data.shape
    # validation
    run(model, train_config, val_data, epoch+1, handle_dict)
    save_env()
    #enc_sched.step(); dec_sched.step()
