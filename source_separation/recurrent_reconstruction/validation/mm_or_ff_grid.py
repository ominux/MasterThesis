from __future__ import division
import sys
sys.path.append('/home/dneil/lasagne')
import numpy as np
import lasagne
import theano
import time
import theano.tensor as T
from lasagne.nonlinearities import rectify, tanh, sigmoid
from lasagne. updates import adam
from scipy.io import loadmat, savemat
import time
import cPickle as pkl

if __name__ == "__main__":

    index_timit = int(sys.argv[1])
    tpe = int(sys.argv[2])  # 0 mm, 1 ff


    def indices(a, func):
        return [i for (i, val) in enumerate(a) if func(val)]


    def create_batches(n_samples, train=True):
        show = False
        if train:
            sel_mix = train_x
            sel_m = train_m
            sel_f = train_f
            batch_x = np.zeros((n_samples, max_len, n_features)).astype(theano.config.floatX)
            batch_m = np.zeros((n_samples, max_len, n_features)).astype(theano.config.floatX)
            batch_f = np.zeros((n_samples, max_len, n_features)).astype(theano.config.floatX)
            idx = np.random.permutation(sel_mix.shape[0] - max_len)
            beg = idx[:n_samples]
            for i, b in enumerate(beg):
                batch_x[i] = sel_mix[b:b + max_len]
                batch_m[i, :, :] = sel_m[b:b + max_len]
                batch_f[i, :, :] = sel_f[b:b + max_len]

        else:
            sel_mix = test_x
            sel_m = test_m
            sel_f = test_f
            Q = int(sel_mix.shape[0] / max_len)
            batch_x = np.zeros((Q, max_len, n_features)).astype(theano.config.floatX)
            batch_m = np.zeros((Q, max_len, n_features)).astype(theano.config.floatX)
            batch_f = np.zeros((Q, max_len, n_features)).astype(theano.config.floatX)
            for i in range(Q):
                batch_x[i] = sel_mix[i*max_len:((i+1)*max_len)]
                batch_m[i, :, :] = sel_m[i*max_len:((i+1)*max_len)]
                batch_f[i, :, :] = sel_f[i*max_len:((i+1)*max_len)]
        return batch_x, batch_m, batch_f

    #fs = 16
    xtr_load = []
    if tpe is 0:
        xtr_load = 'MM'
    if tpe is 1:
        xtr_load = 'FF'

    train_m = loadmat('data/GRID_{}_{}.mat'.format(index_timit, xtr_load))['PWRa']
    train_f = loadmat('data/GRID_{}_{}.mat'.format(index_timit, xtr_load))['PWRb']
    train_x = loadmat('data/GRID_{}_{}.mat'.format(index_timit, xtr_load))['PWR']
    test_m = loadmat('data/GRID_{}_{}.mat'.format(index_timit, xtr_load))['PWRatest']
    test_f = loadmat('data/GRID_{}_{}.mat'.format(index_timit, xtr_load))['PWRbtest']
    test_x = loadmat('data/GRID_{}_{}.mat'.format(index_timit, xtr_load))['PWRtest']

    n_features = train_m.shape[1]  # this time they are 512
    nonlin = sigmoid

    max_len = 50

    NUM_UNITS_ENC = 500
    NUM_UNITS_DEC = 500

    x_sym = T.tensor3()
    mask_x_sym = T.matrix()
    m_sym = T.tensor3()
    f_sym = T.tensor3()
    mask_m_sym = T.tensor3()
    mask_f_sym = T.tensor3()
    n_sym = T.tensor3()
    mask_n_sym = T.tensor3()

    l_in = lasagne.layers.InputLayer(shape=(None, max_len, n_features))

    l_dec_fwd = lasagne.layers.GRULayer(l_in, num_units=NUM_UNITS_DEC, name='GRUDecoder', backwards=False)
    l_dec_bwd = lasagne.layers.GRULayer(l_in, num_units=NUM_UNITS_DEC, name='GRUDecoder', backwards=True)

    l_concat = lasagne.layers.ConcatLayer([l_dec_fwd, l_dec_bwd], axis=2)

    l_encoder_2_m = lasagne.layers.GRULayer(l_concat, num_units=NUM_UNITS_ENC)
    l_encoder_2_f = lasagne.layers.GRULayer(l_concat, num_units=NUM_UNITS_ENC)

    l_encoder_3_m = lasagne.layers.GRULayer(l_encoder_2_m, num_units=NUM_UNITS_ENC)
    l_encoder_3_f = lasagne.layers.GRULayer(l_encoder_2_f, num_units=NUM_UNITS_ENC)

    l_decoder_m = lasagne.layers.GRULayer(l_encoder_3_m, num_units=NUM_UNITS_DEC)
    l_decoder_f = lasagne.layers.GRULayer(l_encoder_3_f, num_units=NUM_UNITS_DEC)
    
    inter_out_m = lasagne.layers.get_output(l_decoder_m, inputs={l_in: x_sym}) 
    inter_out_f = lasagne.layers.get_output(l_decoder_f, inputs={l_in: x_sym})

    l_reshape_m = lasagne.layers.ReshapeLayer(l_decoder_m, (-1, NUM_UNITS_DEC))
    l_dense_m = lasagne.layers.DenseLayer(l_reshape_m, num_units=n_features, nonlinearity=nonlin)
    l_out_m = lasagne.layers.ReshapeLayer(l_dense_m, (-1, max_len, n_features))

    l_reshape_f = lasagne.layers.ReshapeLayer(l_decoder_f, (-1, NUM_UNITS_DEC))
    l_dense_f = lasagne.layers.DenseLayer(l_reshape_f, num_units=n_features, nonlinearity=nonlin)
    l_out_f = lasagne.layers.ReshapeLayer(l_dense_f, (-1, max_len, n_features))

    output_m = lasagne.layers.get_output(l_out_m, inputs={l_in: x_sym})
    output_f = lasagne.layers.get_output(l_out_f, inputs={l_in: x_sym})

    loss_all_m = lasagne.objectives.squared_error(output_m * x_sym, m_sym) + \
                 lasagne.objectives.squared_error((1. - output_m) * x_sym, f_sym)
    loss_all_f = lasagne.objectives.squared_error(output_f * x_sym, f_sym) + \
                 lasagne.objectives.squared_error((1. - output_f) * x_sym, m_sym)
    loss_mean_m = T.mean(loss_all_m)
    loss_mean_f = T.mean(loss_all_f)



    all_params_target_m = lasagne.layers.get_all_params([l_out_m])
    all_grads_target_m = [T.clip(g, -10, 10) for g in T.grad(loss_mean_m, all_params_target_m)]
    all_grads_target_m = lasagne.updates.total_norm_constraint(all_grads_target_m, 10)
    updates_target_m = adam(all_grads_target_m, all_params_target_m)

    train_model_m = theano.function([x_sym, m_sym, f_sym],
                                    [loss_mean_m, output_m, inter_out_m],
                                    updates=updates_target_m,
                                    on_unused_input='ignore')

    test_model_m = theano.function([x_sym, m_sym, f_sym],
                                   [loss_mean_m, output_m, inter_out_m],
                                   on_unused_input='ignore')

    all_params_target_f = lasagne.layers.get_all_params([l_out_f])
    all_grads_target_f = [T.clip(g, -10, 10) for g in T.grad(loss_mean_f, all_params_target_f)]
    all_grads_target_f = lasagne.updates.total_norm_constraint(all_grads_target_f, 10)
    updates_target_f = adam(all_grads_target_f, all_params_target_f)
    train_model_f = theano.function([x_sym, f_sym, m_sym],
                                    [loss_mean_f, output_f, inter_out_f],
                                    updates=updates_target_f,
                                    on_unused_input='ignore')

    test_model_f = theano.function([x_sym, f_sym, m_sym],
                                   [loss_mean_f, output_f, inter_out_f],
                                   on_unused_input='ignore')

    num_min_batches = 100
    n_batch = 120
    epochs = 50
    for i in range(epochs):
        start_time = time.time()
        loss_train_m = 0
        loss_train_f = 0
        for j in range(10):
            batch_x, batch_m, batch_f = create_batches(n_batch)
            loss_m, _, debug_train_m = train_model_m(batch_x, batch_m, batch_f)
            loss_train_m += loss_m

            #loss_f, _, debug_train_f = train_model_f(batch_x, batch_f, batch_m)
            #loss_train_f += loss_f
        print 'M loss %.10f' % (loss_train_m / 10)
        #print 'F loss %.10f' % (loss_train_f / 10)


        batch_test_x, batch_test_m, batch_test_f = create_batches(100, False)
        loss_test_m, out_m, _ = test_model_m(batch_test_x, batch_test_m, batch_test_f)
        #loss_test_f, out_f, _ = test_model_f(batch_test_x, batch_test_f, batch_test_m)
        stop_time = time.time() - start_time
        print ('-'*5 + ' epoch = %i ' + '-'*5 + ' time = %.4f ' + '-'*5) % (i, stop_time)
        print 'M loss TEST = %.10f ' % loss_test_m,
        #print 'F loss TEST = %.10f ' % loss_test_f
        print '-'*20

    # final test
    test_x, test_m, test_f = create_batches(100, False)
    l_m, out_m, debug_test_m = test_model_m(test_x, test_m, test_f)
    out_out_m = out_m
    print 'M TEST = %.10f' % l_m

    #l_f, out_f, debug_test_f = test_model_f(test_x, test_f, test_m)
    #out_out_f = out_f
    #print 'F TEST = %.10f' % l_f

    date = time.strftime("%H:%M_%d:%m:%Y")

    savemat('results/mm_ff/mse_GRID_{}_{}.mat'.format(index_timit, xtr_load), {'out_out_m': out_out_m})
                                        #                                       'out_out_f': out_out_f})

