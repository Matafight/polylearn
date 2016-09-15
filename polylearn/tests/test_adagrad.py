from nose.tools import assert_less_equal

import numpy as np
from numpy.testing import assert_array_almost_equal, assert_array_less

import scipy.sparse as sp

from sklearn.metrics import mean_squared_error

from polylearn.kernels import _poly_predict
from polylearn import FactorizationMachineRegressor
from .test_kernels import dumb_anova_grad


def sg_adagrad_slow(P, X, y, degree, beta, max_iter, learning_rate):

    n_samples = X.shape[0]
    n_components = P.shape[0]

    grad_norms = np.zeros_like(P)

    for it in range(max_iter):

        for i in range(n_samples):
            x = X[i]
            y_pred = _poly_predict(np.atleast_2d(x), P, np.ones(n_components),
                                   kernel='anova', degree=degree)

            for s in range(n_components):
                update = dumb_anova_grad(x, P[s], degree)
                update *= y_pred - y[i]

                grad_norms[s] += update ** 2

                P[s] = P[s] * np.sqrt(grad_norms[s]) - learning_rate * update
                P[s] /= 1e-6 + np.sqrt(grad_norms[s]) + learning_rate * beta

    return P


n_components = 3
n_features = 15
n_samples = 20

rng = np.random.RandomState(1)

X = rng.randn(n_samples, n_features)
P = rng.randn(n_components, n_features)

lams = np.ones(n_components)


class LossCallback(object):

    def __init__(self, X, y):
        self.X = X
        self.y = y
        self.objectives_ = []

    def __call__(self, fm, it):
        y_pred = fm.predict(self.X)
        obj = ((y_pred - self.y) ** 2).mean()
        obj += fm.alpha * (fm.w_ ** 2).sum()
        obj += fm.beta * (fm.P_ ** 2).sum()
        self.objectives_.append(obj)


def check_adagrad_decrease(degree):
    y = _poly_predict(X, P, lams, kernel="anova", degree=degree)

    cb = LossCallback(X, y)
    est = FactorizationMachineRegressor(degree=degree, n_components=3,
                                        fit_linear=True, fit_lower=None,
                                        solver='adagrad',
                                        init_lambdas='ones',
                                        max_iter=100,
                                        learning_rate=0.01,
                                        beta=1e-8,
                                        callback=cb,
                                        n_calls=1,
                                        random_state=0)
    est.fit(X, y)
    obj = np.array(cb.objectives_)
    assert_array_less(obj[1:], obj[:-1])


def test_adagrad_decrease():
    for degree in range(2, 6):
        yield check_adagrad_decrease, degree


def check_adagrad_fit(degree):
    y = _poly_predict(X, P, lams, kernel="anova", degree=degree)

    est = FactorizationMachineRegressor(degree=degree, n_components=3,
                                        fit_linear=True, fit_lower=None,
                                        solver='adagrad',
                                        init_lambdas='ones',
                                        max_iter=30000,
                                        learning_rate=0.1,
                                        beta=1e-8,
                                        random_state=0)

    est.fit(X, y)
    y_pred = est.predict(X)
    err = mean_squared_error(y, y_pred)

    assert_less_equal(err, 1e-3,
        msg="Error {} too big for degree {}.".format(err, degree))


def test_adagrad_fit():
    for degree in range(2, 6):
        yield check_adagrad_fit, degree


def check_adagrad_same_as_slow(degree, sparse):

    beta = 0.00001
    lr = 0.01

    if sparse:
        this_X = X.copy()
        this_X[np.abs(this_X) < 1] = 0
        this_X_sp = sp.csr_matrix(this_X)
    else:
        this_X = this_X_sp = X

    y = _poly_predict(X, P, lams, kernel="anova", degree=degree)

    P_fast = 0.01 * np.random.RandomState(42).randn(1, P.shape[0], P.shape[1])
    P_slow = P_fast[0].copy()

    reg = FactorizationMachineRegressor(degree=degree, n_components=P.shape[0],
                                        fit_lower=None, fit_linear=False,
                                        solver='adagrad', init_lambdas='ones',
                                        beta=beta, warm_start=True,
                                        max_iter=2, learning_rate=lr,
                                        random_state=0)
    reg.P_ = P_fast
    reg.fit(this_X_sp, y)

    P_slow = sg_adagrad_slow(P_slow, this_X, y, degree, beta=beta, max_iter=2,
                             learning_rate=lr)

    assert_array_almost_equal(reg.P_[0, :, :], P_slow)


def test_adagrad_same_as_slow():
    for sparse in (False, True):
        for degree in range(2, 5):
            yield check_adagrad_same_as_slow, degree, sparse