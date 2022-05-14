import torch
import models
from config import cfg
from .nonparam import CVM, KS
from .ksd import KSD
from .mmd import MMD
from .lrt import LRT
from .hst import HST


class GoodnessOfFit:
    def __init__(self, test_mode, alter_num_samples, alter_noise, alpha=0.05):
        self.test_mode = test_mode
        self.alter_num_samples = alter_num_samples
        self.alter_noise = alter_noise
        self.alpha = alpha
        self.gof = self.make_gof()
        self.statistic = []
        self.pvalue = []

    def make_gof(self):
        if self.test_mode == 'cvm':
            gof = CVM()
        elif self.test_mode == 'ks':
            gof = KS()
        elif self.test_mode == 'ksd-u':
            gof = KSD(cfg['num_bootstrap'], False)
        elif self.test_mode == 'ksd-v':
            gof = KSD(cfg['num_bootstrap'], True)
        elif self.test_mode == 'mmd':
            gof = MMD(cfg['num_bootstrap'])
        elif self.test_mode in ['lrt-b-g', 'lrt-b-e']:
            gof = LRT(cfg['num_bootstrap'], True)
        elif self.test_mode in ['lrt-chi2-g', 'lrt-chi2-e']:
            gof = LRT(cfg['num_bootstrap'], False)
        elif self.test_mode in ['hst-b-g', 'hst-b-e']:
            gof = HST(cfg['num_bootstrap'], True)
        elif self.test_mode in ['hst-chi2-g', 'hst-chi2-e']:
            gof = HST(cfg['num_bootstrap'], False)
        else:
            raise ValueError('Not valid test mode')
        return gof

    def test(self, input):
        alter_noise = cfg['alter_noise']
        alter_num_samples = cfg['alter_num_samples']
        null, alter, null_param, alter_param = input['null'], input['alter'], input['null_param'], input['alter_param']
        alter = alter + alter_noise * torch.randn(alter.size(), device=alter.device)
        null_samples = null
        alter_samples = torch.split(alter, alter_num_samples, dim=0)
        if len(alter_samples) % alter_num_samples != 0:
            alter_samples = alter_samples[:-1]
        alter_samples = torch.stack(alter_samples, dim=0)
        if self.test_mode in ['cvm', 'ks']:
            alter_samples = alter_samples.cpu().numpy()
            null_model = eval('models.{}(null_param).to(cfg["device"])'.format(cfg['model_name']))
            statistic, pvalue = self.gof.test(alter_samples, null_model)
        elif self.test_mode in ['ksd-u', 'ksd-v']:
            null_samples = null_samples
            alter_samples = alter_samples
            null_model = eval('models.{}(null_param).to(cfg["device"])'.format(cfg['model_name']))
            statistic, pvalue = self.gof.test(null_samples, alter_samples, null_model)
        elif self.test_mode in ['mmd']:
            null_samples = null_samples
            alter_samples = alter_samples
            statistic, pvalue = self.gof.test(null_samples, alter_samples)
        elif self.test_mode in ['lrt-chi2-g', 'lrt-b-g']:
            null_samples = null_samples
            alter_samples = alter_samples
            null_model = eval('models.{}(null_param).to(cfg["device"])'.format(cfg['model_name']))
            alter_model = eval('models.{}(alter_param).to(cfg["device"])'.format(cfg['model_name']))
            statistic, pvalue = self.gof.test(null_samples, alter_samples, null_model, alter_model)
        elif self.test_mode in ['lrt-chi2-e', 'lrt-b-e']:
            null_samples = null_samples
            alter_samples = alter_samples
            null_model = eval('models.{}(null_param).to(cfg["device"])'.format(cfg['model_name']))
            statistic, pvalue = self.gof.test(null_samples, alter_samples, null_model)
        elif self.test_mode in ['hst-chi2-g', 'hst-b-g']:
            null_samples = null_samples
            alter_samples = alter_samples
            null_model = eval('models.{}(null_param).to(cfg["device"])'.format(cfg['model_name']))
            alter_model = eval('models.{}(alter_param).to(cfg["device"])'.format(cfg['model_name']))
            statistic, pvalue = self.gof.test(null_samples, alter_samples, null_model, alter_model)
        elif self.test_mode in ['hst-chi2-e', 'hst-b-e']:
            null_samples = null_samples
            alter_samples = alter_samples
            null_model = eval('models.{}(null_param).to(cfg["device"])'.format(cfg['model_name']))
            statistic, pvalue = self.gof.test(null_samples, alter_samples, null_model)
        else:
            raise ValueError('Not valid test mode')
        output = {'statistic': statistic, 'pvalue': pvalue}
        return output

    def update(self, output):
        self.statistic.append(output['statistic'])
        self.pvalue.append(output['pvalue'])
        return
