import os
import torch
import hashlib
from torch.utils.data import Dataset
from utils import check_exists, makedir_exist_ok, save, load


class MVN(Dataset):
    data_name = 'MVN'

    def __init__(self, root, **params):
        self.root = os.path.expanduser(root)
        self.num_trials = params['num_trials']
        self.num_samples = params['num_samples']
        self.mean = params['mean']
        self.logvar = params['logvar']
        self.ptb_mean = params['ptb_mean']
        self.ptb_logvar = params['ptb_logvar']
        hash_name = '_'.join([str(params[x]) for x in params]).encode('utf-8')
        m = hashlib.sha256(hash_name)
        self.footprint = m.hexdigest()
        if not check_exists(self.processed_folder):
            self.process()
        self.null, self.alter, self.meta = load(os.path.join(self.processed_folder, 'MVN_{}'.format(self.footprint)),
                                                mode='pickle')

    def __getitem__(self, index):
        null, alter = torch.tensor(self.null[index]), torch.tensor(self.alter[index])
        null_param = {'mean': torch.tensor(self.mean),
                      'logvar': torch.tensor(self.logvar)}
        alter_param = {'mean': torch.tensor(self.meta['mean'][index]),
                       'logvar': torch.tensor(self.meta['logvar'][index])}
        input = {'null': null, 'alter': alter, 'null_param': null_param, 'alter_param': alter_param}
        return input

    def __len__(self):
        return len(self.data)

    @property
    def processed_folder(self):
        return os.path.join(self.root, 'processed')

    @property
    def raw_folder(self):
        return os.path.join(self.root, 'raw')

    def process(self):
        if not check_exists(self.raw_folder):
            self.download()
        dataset = self.make_data()
        save(dataset, os.path.join(self.processed_folder, 'MVN_{}'.format(self.footprint)), mode='pickle')
        return

    def download(self):
        makedir_exist_ok(self.raw_folder)
        return

    def __repr__(self):
        fmt_str = 'Dataset {}\nSize: {}\nRoot: {}\nFootprint: {}'.format(
            self.__class__.__name__, self.__len__(), self.root, self.footprint)
        return fmt_str

    def make_data(self):
        total_samples = self.num_trials * self.num_samples
        d = self.mean.size(0)
        null_mvn = torch.distributions.multivariate_normal.MultivariateNormal(self.mean, self.logvar.exp())
        null = null_mvn.sample((total_samples,))
        null = null.view(self.num_trials, self.num_samples, -1)
        ptb_mean = self.ptb_mean * torch.randn((self.num_trials, *self.mean.size()))
        alter_mean = self.mean + ptb_mean
        ptb_logvar = torch.diag_embed(self.ptb_logvar * torch.randn((self.num_trials, d)))
        alter_logvar = self.logvar + ptb_logvar
        alter_normal = torch.distributions.multivariate_normal.MultivariateNormal(alter_mean, self.logvar.exp())
        alter = alter_normal.sample((self.num_samples,))
        alter = alter.permute(1, 0, 2)
        null, alter = null.numpy(), alter.numpy()
        meta = {'mean': alter_mean.numpy(), 'logvar': alter_logvar.numpy()}
        return null, alter, meta