import lasagne
import theano
import theano.tensor as T
import numpy as np
import time as tm
from lasagne.nonlinearities import rectify,identity, tanh
from scipy.io import loadmat, savemat
from lasagne.layers import InputLayer, DenseLayer, DropoutLayer, Layer
from theano.sandbox.rng_mrg import MRG_RandomStreams as RandomStreams
from lasagne import init
from lasagne.updates import adam
from matplotlib import pyplot as plt
from lasagne.regularization import l2


def createMLP(layers, s):
    l_in = lasagne.layers.InputLayer(shape=(None, s))
    prev_layer = l_in
    Ws = []
    for layer in layers:
        enc = lasagne.layers.DenseLayer(prev_layer, num_units=layer, nonlinearity=rectify, W=init.Uniform(0.01))
        Ws += [enc.W]
        drop = lasagne.layers.DropoutLayer(enc, p=0.5)
        prev_layer = drop
    idx = 1
    # creating mask
    mask = lasagne.layers.InputLayer(shape=(None, layers[-1]))
    prev_layer = lasagne.layers.ElemwiseMergeLayer([prev_layer, mask], merge_function=T.mul)
    for layer in layers[-2::-1]:
        print layer
        dec = lasagne.layers.DenseLayer(prev_layer, num_units=layer, nonlinearity=rectify, W=Ws[-idx].T)
        idx += 1
        drop = lasagne.layers.DropoutLayer(dec, p=0.0)
        prev_layer = drop
    model = lasagne.layers.DenseLayer(prev_layer, num_units=s, nonlinearity=identity, W=Ws[0].T)

    x_sym = T.dmatrix()
    mask_sym = T.dmatrix()
    all_params = lasagne.layers.get_all_params(model)
    output = lasagne.layers.get_output(model, inputs={l_in: x_sym, mask: mask_sym})
    loss_eval = lasagne.objectives.squared_error(output, x_sym).sum()
    loss_eval /= (2.*batch_size)
    updates = lasagne.updates.adam(loss_eval, all_params)

    return l_in, mask, model, theano.function([x_sym, mask_sym], loss_eval, updates=updates)









####

rng = np.random.RandomState(42)
cor = loadmat('../data/come_done_COR_5R.mat')['COR']
rec_cor_1 = np.zeros_like(cor)
rec_cor_2 = np.zeros_like(cor)
# so the dataset is created online, for every timestep I need to compute the C-mat and train a new VAE with that
time, freq, rates = cor.shape
d = freq * rates / 2
c_mat = np.zeros(shape=(freq+1, d))
all_params = None
a2 = 512
# fake data for debugginf
x_sym = T.dmatrix()
latent_sym = T.dmatrix()
mask_sym = T.dmatrix()
x_fake = np.ones((64, d))
x_fake_2 = np.ones((32, d))


n_epochs = 200
batch_size = 500
layers = [200, 2]
Ws = []


l_in = lasagne.layers.InputLayer(shape=(None, a2))
prev_layer = l_in

for layer in layers:
    enc = lasagne.layers.DenseLayer(prev_layer, num_units=layer, nonlinearity=rectify, W=init.Uniform(0.1))
    Ws += [enc.W]
    drop = lasagne.layers.DropoutLayer(enc, p=0.5)
    prev_layer = drop

idx = 1

# creating mask
mask = lasagne.layers.InputLayer(shape=(None, layers[-1]))
prev_layer = lasagne.layers.ElemwiseMergeLayer([prev_layer, mask], merge_function=T.mul)
for layer in layers[-2::-1]:
    print layer
    dec = lasagne.layers.DenseLayer(prev_layer, num_units=layer, nonlinearity=rectify, W=Ws[-idx].T)
    idx += 1
    drop = lasagne.layers.DropoutLayer(dec, p=0.0)
    prev_layer = drop
model = lasagne.layers.DenseLayer(prev_layer, num_units=a2, nonlinearity=identity, W=Ws[0].T)


x_sym = T.dmatrix()
mask_sym = T.dmatrix()
all_params = lasagne.layers.get_all_params(model)
output = lasagne.layers.get_output(model, inputs={l_in: x_sym, mask: mask_sym})
loss_eval = lasagne.objectives.squared_error(output, x_sym).sum()
loss_eval /= (2.*batch_size)


updates = lasagne.updates.adam(loss_eval, all_params)

train_model = theano.function([x_sym, mask_sym], loss_eval, updates=updates)

x_sym = T.dmatrix()

l_in, mask_layer, model, train_model = createMLP(layers, a2)


mask = np.zeros(((freq+1)*rates/2, 2))
mask[:, 0] = 1
mask_training = np.ones(((freq+1)*rates/2, 2))

for t in range(time):
    x = cor[t, :, :]
    x_prime = np.zeros((d, 1))
    for rate in range(rates/2):
        d11 = x[:, rate]
        d1 = np.outer(d11, d11)
        d22 = x[:, rates/2 + rate]
        d2 = np.outer(d22, d22)
        x_prime[rate*freq:(rate+1)*freq, 0] = np.real((d11 + d22) / 2)
        c_mat[:-1, slice(rate * freq, (rate + 1) * freq)] = np.real((d1 + d2) / 2)
    x_prime = x_prime.transpose()
    c_mat[-1, :] = x_prime
    c_mat_lim = c_mat.reshape((freq+1)*rates/2, freq)
    print c_mat_lim.shape
    for epoch in range(n_epochs):
        # c_mat_sc = c_mat[np.random.randint(0, freq+1, size=(freq + 1))]
        # c_mat_sc += rng.rand(c_mat_sc.shape[0], c_mat_sc.shape[1]) / (np.max(c_mat_sc) * 10)
        # for i in range(8):
        eval_train = train_model(c_mat_lim, mask_training)
        print "Layer %i %.10f (time=%i)" % (layer, eval_train, epoch)

    c_recon = lasagne.layers.get_output(model, {l_in: x_sym, mask_layer: mask_sym}, deterministic=True).eval({x_sym: c_mat_lim, mask_sym: mask})

    fig = plt.figure()
    plt.subplot(1, 2, 1)
    plt.imshow(c_mat_lim, interpolation='nearest', aspect='auto')
    plt.subplot(1, 2, 2)
    plt.imshow(c_recon, interpolation='nearest', aspect='auto')
    plt.colorbar()
    plt.show()
    # print dec_from_enc1
savemat('come_done_filtered.mat', {'rec_cor_1': rec_cor_1, 'rec_cor_2': rec_cor_2})


#
# dec = lasagne.layers.get_output(model, inputs={l_in: x_sym}).eval({x_sym: test_x})
# fig = plt.figure()
# i = 0
# test_x_eval = test_x
# subset = np.random.randint(0, len(test_x_eval), size=50)
# img_out = np.zeros((28 * 2, 28 * len(subset)))
# x = np.array(test_x_eval)[np.array(subset)]
# for y in range(len(subset)):
#     x_a, x_b = 0 * 28, 1 * 28
#     x_recon_a, x_recon_b = 1 * 28, 2 * 28
#     ya, yb = y * 28, (y + 1) * 28
#     im = np.reshape(x[i], (28, 28))
#     im_recon = np.reshape(dec[subset[i]], (28, 28))
#     img_out[x_a:x_b, ya:yb] = im
#     img_out[x_recon_a:x_recon_b, ya:yb] = im_recon
#     i += 1
# m = plt.matshow(img_out, cmap='gray')
# plt.xticks(np.array([]))
# plt.yticks(np.array([]))
# plt.show()
