import numpy as np
import torch
import models
from scipy.stats import chi2
from config import cfg

class LRT:
    def __init__(self, num_bootstrap, bootstrap_approx):
        super().__init__()
        self.num_bootstrap = num_bootstrap
        self.bootstrap_approx = bootstrap_approx

    def test(self, null_samples, alter_samples, null_model, alter_model=None):
        num_tests = alter_samples.size(0)
        num_samples_alter = alter_samples.size(1)
        with torch.no_grad():
            statistic = []
            pvalue = []
            for i in range(num_tests):
                if alter_model is None:
                    alter_model = eval('models.{}(null_model.params).to(cfg["device"])'.format(cfg['model_name']))
                    alter_model.fit(alter_samples[i])
                bootstrap_null_samples = self.multinomial_bootstrap(null_samples, num_samples_alter, null_model,
                                                                    alter_model)
                # bootstrap_null_samples = self.m_out_n_bootstrap(null_samples, num_samples_alter, null_model, alter_model)
                statistic_i, pvalue_i = self.density_test(alter_samples[i], bootstrap_null_samples, null_model,
                                                          alter_model, self.bootstrap_approx)
                statistic.append(statistic_i)
                pvalue.append(pvalue_i)
        return statistic, pvalue

    def m_out_n_bootstrap(self, null_samples, num_samples_alter, null_model, alter_model):
        num_samples_null = null_samples.size(0)
        """Bootstrap algorithm (m out of n) for hypothesis testing by Bickel & Ren (2001)"""
        null_items, _ = self.lrt(null_samples, null_model.pdf, alter_model.pdf)
        _index = torch.multinomial(
            null_items.new_ones(num_samples_null).repeat(self.num_bootstrap, 1) / num_samples_null, num_samples_alter,
            replacement=True)
        null_items = null_items.repeat(self.num_bootstrap, 1)
        bootstrap_null_items = torch.gather(null_items, 1, _index)
        bootstrap_null_samples = torch.sum(bootstrap_null_items, dim=-1)
        return bootstrap_null_samples

    def multinomial_bootstrap(self, null_samples, num_samples_alter, null_model, alter_model):
        """Bootstrap algorithm for U-statistics by Huskova & Janssen (1993)"""
        null_items, _ = self.lrt(null_samples[:num_samples_alter], null_model.pdf, alter_model.pdf)
        weights_exp1, weights_exp2 = self.multinomial_weights(num_samples_alter)
        weights_exp1, weights_exp2 = weights_exp1.to(null_samples.device), weights_exp2.to(null_samples.device)
        null_items = torch.unsqueeze(null_items, dim=0)  # 1 x N x N
        bootstrap_null_samples = (weights_exp1 - 1. / num_samples_alter) * null_items * (
                weights_exp2 - 1. / num_samples_alter)  # m x N x N
        bootstrap_null_samples = torch.sum(torch.sum(bootstrap_null_samples, dim=-1), dim=-1)
        return bootstrap_null_samples

    def multinomial_weights(self, num_samples):
        """Sample multinomial weights for bootstrap by Huskova & Janssen (1993)"""
        weights = np.random.multinomial(num_samples, np.ones(num_samples) / num_samples, size=self.num_bootstrap)
        weights = weights / num_samples
        weights = torch.from_numpy(weights)
        weights_exp1 = torch.unsqueeze(weights, dim=-1)  # m x N x 1
        weights_exp2 = torch.unsqueeze(weights, dim=1)  # m x 1 x N
        return weights_exp1, weights_exp2

    def lrt(self, samples, null_pdf, alter_pdf):
        """Calculate Likelihood Ratio"""
        LRT_items = 2 * (torch.log(alter_pdf(samples)) - torch.log(null_pdf(samples)))
        LRT_items = LRT_items.reshape(-1)
        test_statistic = torch.sum(LRT_items, -1)
        return LRT_items, test_statistic

    def density_test(self, alter_samples, bootstrap_null_samples, null_model, alter_model, bootstrap_approx):
        _, test_statistic = self.lrt(alter_samples, null_model.pdf, alter_model.pdf)
        test_statistic = test_statistic.item()
        if bootstrap_approx:
            pvalue = torch.mean((bootstrap_null_samples > test_statistic).float()).item()
        else:
            df = 1
            pvalue = 1 - chi2(df).cdf(test_statistic)  # since Λ follows χ2
        return test_statistic, pvalue
