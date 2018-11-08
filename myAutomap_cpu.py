#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Nov  5 13:04:46 2018

@author: cduan
"""

import numpy as np
import tensorflow as tf
from tensorflow.python.framework import ops
import math
import time
import matplotlib.pyplot as plt
from generate_input import load_STONE_data


# Load training data, cropped and resized from MATLAB
tic1 = time.time()
dir_train = "/home/chongduan/Documents/Automap-MRI/Dataset"
n_cases = (0,1)
X_train, Y_train = load_STONE_data( 
    dir_train,
    n_cases,
    normalize=False,
    imrotate=False,
    motion=True)
toc1 = time.time()
print('Time to load data = ', (toc1 - tic1))
print('X_train.shape at input = ', X_train.shape)
print('Y_train.shape at input = ', Y_train.shape)


def create_placeholders(n_H0, n_W0):
    """ Creates placeholders for x and y for tf.session
    :param n_H0: image height
    :param n_W0: image width
    :return: x and y - tf placeholders
    """

    x = tf.placeholder(tf.float32, shape=[None, n_H0, n_W0, 2], name='x')
    y = tf.placeholder(tf.float32, shape=[None, n_H0, n_W0], name='y')

    return x, y

def forward_propagation(x):
    """ Defines all layers for forward propagation:
    Fully connected (FC1) -> tanh activation: size (n_im, n_H0 * n_W0)
    -> Fully connected (FC2) -> tanh activation:  size (n_im, n_H0 * n_W0)
    -> Convolutional -> ReLU activation: size (n_im, n_H0, n_W0, 64)
    -> Convolutional -> ReLU activation with l1 regularization: size (n_im, n_H0, n_W0, 64)
    -> De-convolutional: size (n_im, n_H0, n_W0)
    :param x: Input - images in frequency space, size (n_im, n_H0, n_W0, 2)
    :param parameters: parameters of the layers (e.g. filters)
    :return: output of the last layer of the neural network
    """

    x_temp = tf.contrib.layers.flatten(x)  # size (n_im, n_H0 * n_W0 * 2)
    n_out = np.int(x.shape[1] * x.shape[2])  # size (n_im, n_H0 * n_W0)

    # FC: input size (n_im, n_H0 * n_W0 * 2), output size (n_im, n_H0 * n_W0)
    FC1 = tf.contrib.layers.fully_connected(
        x_temp,
        n_out,
        activation_fn=tf.tanh,
        normalizer_fn=None,
        normalizer_params=None,
        weights_initializer=tf.contrib.layers.xavier_initializer(),
        weights_regularizer=None,
        biases_initializer=None,
        biases_regularizer=None,
        reuse=tf.AUTO_REUSE,
        variables_collections=None,
        outputs_collections=None,
        trainable=True,
        scope='fc1')

    # FC: input size (n_im, n_H0 * n_W0), output size (n_im, n_H0 * n_W0)
    FC2 = tf.contrib.layers.fully_connected(
        FC1,
        n_out,
        activation_fn=tf.tanh,
        normalizer_fn=None,
        normalizer_params=None,
        weights_initializer=tf.contrib.layers.xavier_initializer(),
        weights_regularizer=None,
        biases_initializer=None,
        biases_regularizer=None,
        reuse=tf.AUTO_REUSE,
        variables_collections=None,
        outputs_collections=None,
        trainable=True,
        scope='fc2')

    # Reshape output from FC layers into array of size (n_im, n_H0, n_W0, 1):
    FC_M = tf.reshape(FC2, [tf.shape(x)[0], tf.shape(x)[1], tf.shape(x)[2], 1])

    CONV1 = tf.layers.conv2d(
        FC_M,
        filters=64,
        kernel_size=5,
        strides=(1, 1),
        padding='same',
        data_format='channels_last',
        dilation_rate=(1, 1),
        activation=tf.nn.relu,
        use_bias=True,
        kernel_initializer=None,
        bias_initializer=tf.zeros_initializer(),
        kernel_regularizer=None,
        bias_regularizer=None,
        activity_regularizer=None,
        kernel_constraint=None,
        bias_constraint=None,
        trainable=True,
        name='conv1',
        reuse=tf.AUTO_REUSE)
    
    CONV2 = tf.layers.conv2d(
        CONV1,
        filters=64,
        kernel_size=5,
        strides=(1, 1),
        padding='same',
        data_format='channels_last',
        dilation_rate=(1, 1),
        activation=tf.nn.relu,
        use_bias=True,
        kernel_initializer=None,
        bias_initializer=tf.zeros_initializer(),
        kernel_regularizer=None,
        bias_regularizer=None,
        activity_regularizer=None,
        kernel_constraint=None,
        bias_constraint=None,
        trainable=True,
        name='conv2',
        reuse=tf.AUTO_REUSE)
    
    # Apply L1-norm on last hidden layer to the activation as described in the paper
    CONV3 = tf.layers.conv2d(
        CONV2,
        filters=1,
        kernel_size=7,
        strides=(1, 1),
        padding='same',
        data_format='channels_last',
        dilation_rate=(1, 1),
        activation=tf.nn.relu,
        use_bias=True,
        kernel_initializer=None,
        bias_initializer=tf.zeros_initializer(),
        kernel_regularizer=None,
        bias_regularizer=None,
#        activity_regularizer = None,
        activity_regularizer=tf.contrib.layers.l1_regularizer(0.0001),
        kernel_constraint=None,
        bias_constraint=None,
        trainable=True,
        name='conv3',
        reuse=tf.AUTO_REUSE)
    
    OUTPUT = tf.squeeze(CONV3)

    return OUTPUT

def compute_cost(OUTPUT, Y):
    """
    Computes cost (squared loss) between the output of forward propagation and
    the label image
    :param DECONV: output of forward propagation
    :param Y: label image
    :return: cost (squared loss)
    """

    cost = tf.square(OUTPUT - Y)

    return cost

def random_mini_batches(x, y, mini_batch_size=64, seed=0):
    """ Shuffles training examples and partitions them into mini-batches
    to speed up the gradient descent
    :param x: input frequency space data
    :param y: input image space data
    :param mini_batch_size: mini-batch size
    :param seed: can be chosen to keep the random choice consistent
    :return: a mini-batch of size mini_batch_size of training examples
    """

    m = x.shape[0]  # number of input images
    mini_batches = []
    np.random.seed(seed)

    # Shuffle (x, y)
    permutation = list(np.random.permutation(m))
    shuffled_X = x[permutation, :]
    shuffled_Y = y[permutation, :]

    # Partition (shuffled_X, shuffled_Y). Minus the end case.
    num_complete_minibatches = int(math.floor(
        m / mini_batch_size))  # number of mini batches of size mini_batch_size

    for k in range(0, num_complete_minibatches):
        mini_batch_X = shuffled_X[k * mini_batch_size:k * mini_batch_size
                                    + mini_batch_size, :, :, :]
        mini_batch_Y = shuffled_Y[k * mini_batch_size:k * mini_batch_size
                                    + mini_batch_size, :, :]
        mini_batch = (mini_batch_X, mini_batch_Y)
        mini_batches.append(mini_batch)

    # Handling the end case (last mini-batch < mini_batch_size)
    if m % mini_batch_size != 0:
        mini_batch_X = shuffled_X[num_complete_minibatches
                                  * mini_batch_size: m, :, :, :]
        mini_batch_Y = shuffled_Y[num_complete_minibatches
                                  * mini_batch_size: m, :, :]
        mini_batch = (mini_batch_X, mini_batch_Y)
        mini_batches.append(mini_batch)

    return mini_batches


def model(X_train, Y_train, learning_rate=0.0001,
          num_epochs=100, minibatch_size=5, print_cost=True):
    """ Runs the forward and backward propagation
    :param X_train: input training frequency-space data
    :param Y_train: input training image-space data
    :param learning_rate: learning rate of gradient descent
    :param num_epochs: number of epochs
    :param minibatch_size: size of mini-batch
    :param print_cost: if True - the cost will be printed every epoch, as well
    as how long it took to run the epoch
    :return: this function saves the model to a file. The model can then
    be used to reconstruct the image from frequency space
    """

    ops.reset_default_graph()  # to not overwrite tf variables
    seed = 3
    (m, n_H0, n_W0, _) = X_train.shape

    # Create Placeholders
    X, Y = create_placeholders(n_H0, n_W0)

#    # Initialize parameters
#    parameters = initialize_parameters()

    # Build the forward propagation in the tf graph
    OUTPUT = forward_propagation(X)

    # Add cost function to tf graph
    cost = compute_cost(OUTPUT, Y)
    
    # Add global_step variable for save training models - Chong Duan
    my_global_step = tf.Variable(0, dtype=tf.int32, trainable=False, name='global_step')
    
    # Backpropagation
    optimizer = tf.train.RMSPropOptimizer(learning_rate,
                                          decay=0.9,
                                          momentum=0.0).minimize(cost, global_step = my_global_step)

    # Initialize all the variables globally
    init = tf.global_variables_initializer()

    # Add ops to save and restore all the variables
    saver = tf.train.Saver(save_relative_paths=True)

    # Memory config
    config = tf.ConfigProto()
    config.gpu_options.allow_growth = True
    config = tf.ConfigProto(log_device_placement=True)

    # Start the session to compute the tf graph
    with tf.Session(config=config) as sess:

        # Initialization
        sess.run(init)

        # Training loop
        learning_curve = []
        for epoch in range(num_epochs):
            tic = time.time()

            minibatch_cost = 0.
            num_minibatches = int(m / minibatch_size)  # number of minibatches
            seed += 1
            minibatches = random_mini_batches(X_train, Y_train,
                                              minibatch_size, seed)
            # Minibatch loop
            for minibatch in minibatches:
                # Select a minibatch
                (minibatch_X, minibatch_Y) = minibatch
                # Run the session to execute the optimizer and the cost
                _, temp_cost = sess.run(
                    [optimizer, cost],
                    feed_dict={X: minibatch_X, Y: minibatch_Y})

                cost_mean = np.mean(temp_cost) / num_minibatches
                minibatch_cost += cost_mean

            # Print the cost every epoch
            learning_curve.append(minibatch_cost)
            if print_cost:
                toc = time.time()
                print ('EPOCH = ', epoch, 'COST = ', minibatch_cost, 'Elapsed time = ', (toc - tic))
                
            if (epoch + 1) % 2 == 0:
                save_path = saver.save(sess, '../checkpoints/model.ckpt', global_step = my_global_step)
                print("Model saved in file: %s" % save_path)

        
        # Plot learning curve
        plt.plot(learning_curve)
        plt.title('Learning Curve')
        plt.xlabel('Epoch')
        plt.ylabel('Cost')
        plt.show()
        
        # Close sess
        sess.close()

# Finally run the model!
model(X_train, Y_train,
      learning_rate=0.0001,
      num_epochs=5,
      minibatch_size=11,  # should be < than the number of input examples
      print_cost=True)