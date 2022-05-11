import os
import torch
import hashlib
from torch.utils.data import Dataset
from utils import check_exists, makedir_exist_ok, save, load


class GMM(Dataset):
    data_name = 'GMM'

    def __init__(self, root, **params):
        super().__init__()
        self.root = os.path.expanduser(root)
        self.num_trials = params['num_trials']
        self.num_samples = params['num_samples']
        self.mean = params['mean']
        self.logvar = params['logvar']
        self.logweight = params['logweight']
        self.ptb_mean = params['ptb_mean']
        self.ptb_logvar = params['ptb_logvar']
        self.ptb_logweight = params['ptb_logweight']
        hash_name = '_'.join([str(params[x]) for x in params]).encode('utf-8')
        m = hashlib.sha256(hash_name)
        self.footprint = m.hexdigest()
        split_name = '{}_{}'.format(self.data_name, self.footprint)
        if not check_exists(os.path.join(self.processed_folder, split_name)):
            self.process()
        self.null, self.alter, self.meta = load(os.path.join(os.path.join(self.processed_folder, split_name)),
                                                mode='pickle')

    def __getitem__(self, index):
        null, alter = torch.tensor(self.null[index]), torch.tensor(self.alter[index])
        null_param = {'logweight': self.logweight, 'mean': self.mean, 'logvar': self.logvar}
        alter_param = {'logweight': torch.tensor(self.meta['logweight'][index]),
                       'mean': torch.tensor(self.meta['mean'][index]),
                       'logvar': torch.tensor(self.meta['logvar'][index])}
        input = {'null': null, 'alter': alter, 'null_param': null_param, 'alter_param': alter_param}
        return input

    def __len__(self):
        return self.num_trials

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
        save(dataset, os.path.join(self.processed_folder, '{}_{}'.format(self.data_name, self.footprint)),
             mode='pickle')
        return

    def download(self):
        makedir_exist_ok(self.raw_folder)
        return

    def __repr__(self):
        fmt_str = 'Dataset {}\nSize: {}\nRoot: {}\nFootprint: {}'.format(self.data_name, self.__len__(), self.root,
                                                                         self.footprint)
        return fmt_str

    def make_data(self):
        total_samples = self.num_trials * self.num_samples
        d = self.mean.size(-1)
        k = self.logweight.size(0)
        null_normal = torch.distributions.multivariate_normal.MultivariateNormal(self.mean, self.logvar.exp())
        null = null_normal.sample((total_samples,))
        null_mixture_idx = torch.multinomial(self.logweight.softmax(dim=-1),
                                             num_samples=self.num_trials * self.num_samples,
                                             replacement=True)
        null_mixture_idx = null_mixture_idx.view(null_mixture_idx.size(0), 1, 1).repeat(1, 1, d)
        null = torch.gather(null, 1, index=null_mixture_idx)
        null = null.squeeze(1).view(self.num_trials, self.num_samples, -1)
        alter_logweight = self.logweight + self.ptb_logweight * torch.randn((self.num_trials, *self.logweight.size()))
        ptb_mean = self.ptb_mean * torch.randn((self.num_trials, *self.mean.size()))
        alter_mean = self.mean + ptb_mean
        ptb_logvar = torch.diag_embed(self.ptb_logvar * torch.randn((self.num_trials * k, d))).view(
            self.num_trials, k, d, d)
        alter_logvar = self.logvar + ptb_logvar
        alter_normal = torch.distributions.multivariate_normal.MultivariateNormal(alter_mean, alter_logvar.exp())
        alter = alter_normal.sample((self.num_samples,))
        alter = alter.permute(1, 0, 2, 3)
        alter_mixture_idx = torch.multinomial(alter_logweight.softmax(dim=-1),
                                              num_samples=self.num_samples,
                                              replacement=True)
        alter_mixture_idx = alter_mixture_idx.view(*alter_mixture_idx.size(), 1, 1).repeat(1, 1, 1, d)
        alter = torch.gather(alter, 2, index=alter_mixture_idx)
        alter = alter.squeeze(2)
        null, alter = null.numpy(), alter.numpy()
        meta = {'logweight': alter_logweight.numpy(), 'mean': alter_mean.numpy(), 'logvar': alter_logvar.numpy()}
        return null, alter, meta
