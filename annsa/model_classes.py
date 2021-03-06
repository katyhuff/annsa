import pickle
import tensorflow as tf
import numpy as np
import tensorflow.contrib.eager as tfe
from sklearn.model_selection import StratifiedKFold
from tensorflow.keras.initializers import lecun_normal, he_normal
import time

# ##############################################################
# ##############################################################
# ##################### Dense Archetecture #####################
# ##############################################################
# ##############################################################
# ##############################################################


class dnn(tf.keras.Model):
    """Defines dense NN structure and training functions.

    """
    def __init__(self, model_features):
        """Initializes dnn structure with model features.

        Args:
            model_features: Class that contains variables
            to construct the dense neural network.

        """
        super(dnn, self).__init__()
        """ Define here the layers used during the forward-pass
            of the neural network.
        """

        self.l2_regularization_scale = model_features.l2_regularization_scale
        dropout_probability = model_features.dropout_probability
        self.dense_nodes = model_features.dense_nodes
        self.batch_size = model_features.batch_size
        self.scaler = model_features.scaler
        output_size = model_features.output_size
        regularizer = tf.contrib.layers.l2_regularizer(
            scale=self.l2_regularization_scale)

        # Define hidden layers.
        self.dense_layers = {}
        self.drop_layers = {}
        for layer, nodes in enumerate(self.dense_nodes):

            self.dense_layers[layer] = tf.layers.Dense(
                nodes,
                activation=tf.nn.relu,
                kernel_initializer=he_normal(),
                kernel_regularizer=regularizer)
            self.drop_layers[layer] = tf.layers.Dropout(dropout_probability)
        self.output_layer = tf.layers.Dense(output_size, activation=None)

    def predict_logits(self, input_data, training=True):
        """ Runs a forward-pass through the network. Only outputs logits for
            loss function. This is because
            tf.nn.softmax_cross_entropy_with_logits calculates softmax
            internally. Note, training is true here to turn dropout on.
            Args:
                input_data: 2D tensor of shape (n_samples, n_features).
            Returns:
                logits: unnormalized predictions.
        """
        x = self.scaler.transform(input_data)
        x = tf.reshape(x, [-1, 1, x.shape[1]])
        for layer, nodes in enumerate(self.dense_nodes):
            x = self.dense_layers[layer](x)
            x = self.drop_layers[layer](x, training)
        logits = self.output_layer(x)

        return logits

    def predict(self, input_data, training=False):
        """ Runs a forward-pass through the network and uses softmax output.
            Dropout training is off, this is not used for gradient calculations
            in loss function.
            Args:
                input_data: 2D tensor of shape (n_samples, n_features).
            Returns:
                logits: unnormalized predictions.
        """
        return tf.nn.softmax(self.predict_logits(self, input_data, training))

    def loss_fn(self, input_data, target, training=True):
        """ Defines the loss function used during
            training.
        """
        logits = self.predict_logits(input_data, training)
        cross_entropy_loss = tf.reduce_mean(
            tf.nn.softmax_cross_entropy_with_logits(
                labels=target,
                logits=logits))
        loss = cross_entropy_loss
        if self.l2_regularization_scale > 0:
            for layer, nodes in enumerate(self.dense_layers):
                loss += self.dense_layers[layer].losses

        return loss

    def grads_fn(self, input_data, target):
        """ Dynamically computes the gradients of the loss value
            with respect to the parameters of the model, in each
            forward pass.
        """
        with tfe.GradientTape() as tape:
            loss = self.loss_fn(input_data, target)
        return tape.gradient(loss, self.variables)

    def fit_batch(self,
                  train_dataset,
                  test_dataset,
                  optimizer,
                  num_epochs=50,
                  verbose=50,
                  print_errors=True,
                  early_stopping_patience=0,
                  max_time=300):
        """ Function to train the model, using the selected optimizer and
            for the desired number of epochs. Uses early stopping with
            patience.
        """
        all_loss_train = []
        all_loss_test = []
        time_start = time.time()
        early_stopping_flag = False
        for epoch in range(num_epochs):
            for (input_data, target) in tfe.Iterator(
                            train_dataset.shuffle(1e8).batch(self.batch_size)):
                input_data = np.random.poisson(input_data).astype(float)
                grads = self.grads_fn(input_data, target)
                optimizer.apply_gradients(zip(grads, self.variables))
                all_loss_train.append(
                    self.loss_fn(input_data, target, training=False).numpy())
                if early_stopping_patience == 0:
                    all_loss_test.append(self.loss_fn(test_dataset[0],
                                                      test_dataset[1],
                                                      training=False).numpy())

            # Save error for early stopping
            if early_stopping_patience != 0:
                all_loss_test.append(self.loss_fn(test_dataset[0],
                                                  test_dataset[1],
                                                  training=False).numpy())
                tmp_min_test_error = all_loss_test[-1]
                if epoch == 0:
                    patience_counter = 0
                    min_test_error = tmp_min_test_error
                elif (epoch > 0) and (tmp_min_test_error < min_test_error):
                    min_test_error = tmp_min_test_error
                    patience_counter = 0
                else:
                    patience_counter += 1
                time_taken = time.time()-time_start
                if ((patience_counter >= early_stopping_patience) or
                        (time_taken > max_time)):
                    early_stopping_flag = True

            if (print_errors and
                    ((epoch == 0) | ((epoch+1) % verbose == 0))) is True:
                print('Loss at epoch %d: %3.2f %3.2f' % (epoch+1,
                                                         all_loss_train[-1],
                                                         all_loss_test[-1]))
            if early_stopping_flag is True:
                break
        return all_loss_train, all_loss_test


class dnn_model_features(object):
    def __init__(self, learining_rate,
                 l2_regularization_scale,
                 dropout_probability,
                 batch_size,
                 output_size,
                 dense_nodes,
                 scaler
                 ):
        self.learining_rate = learining_rate
        self.l2_regularization_scale = l2_regularization_scale
        self.dropout_probability = dropout_probability
        self.batch_size = batch_size
        self.output_size = output_size
        self.dense_nodes = dense_nodes
        self.scaler = scaler

# ##############################################################
# ##############################################################
# ################# Convolutional Archetecture #################
# ##############################################################
# ##############################################################
# ##############################################################


class cnn(tf.keras.Model):
    def __init__(self, model_features):
        super(cnn, self).__init__()
        """ Define here the layers used during the forward-pass
            of the neural network.
        """
        l2_regularization_scale = model_features.l2_regularization_scale
        dropout_probability = model_features.dropout_probability
        nodes_layer_1 = model_features.nodes_layer_1
        nodes_layer_2 = model_features.nodes_layer_2
        input_shape = (-1, 1024, 1)
        number_filters = model_features.number_filters
        kernel_size = model_features.kernel_size
        self.batch_size = model_features.batch_size
        self.scaler = model_features.scaler
        # Convolution layers.
        self.cnn_layer1 = tf.layers.Conv1D(filters=number_filters[0],
                                           kernel_size=kernel_size[0],
                                           strides=1,
                                           padding='valid',
                                           activation='relu')
        self.max_pool1 = tf.layers.MaxPooling1D(pool_size=2,
                                                strides=2,
                                                padding='valid')
        self.cnn_layer2 = tf.layers.Conv1D(filters=number_filters[1],
                                           kernel_size=kernel_size[1],
                                           strides=1,
                                           padding='valid',
                                           activation='relu')
        self.max_pool2 = tf.layers.MaxPooling1D(pool_size=2,
                                                strides=2,
                                                padding='valid')

        # Fully connected layers.
        self.flatten1 = tf.layers.Flatten()
        self.dropout1 = tf.layers.Dropout(dropout_probability)
        self.dense_layer1 = tf.layers.Dense(nodes_layer_1,
                                            kernel_initializer=lecun_normal(),
                                            activation=tf.nn.relu)
        self.dropout2 = tf.layers.Dropout(dropout_probability)
        self.output_layer = tf.layers.Dense(57,
                                            kernel_initializer=lecun_normal(),
                                            activation=None)

    def predict_logits(self, input_data, training=True):
        """ Runs a forward-pass through the network. Only outputs logits for
            loss function. This is because
            tf.nn.softmax_cross_entropy_with_logits calculates softmax
            internally. Note, dropout training is true here.
            Args:
                input_data: 2D tensor of shape (n_samples, n_features).
            Returns:
                logits: unnormalized predictions.
        """
        # Reshape input data
        x = self.scaler.transform(input_data)
        x = tf.reshape(x, [-1, x.shape[1], 1])
        x = self.cnn_layer1(x)
        x = self.max_pool1(x)
        x = self.cnn_layer2(x)
        x = self.max_pool2(x)
        x = self.flatten1(x)
        x = self.dropout1(x)
        x = self.dense_layer1(x)
        x = self.dropout2(x)
        logits = self.output_layer(x)
        return logits

    def loss_fn(self, input_data, target, training=True):
        """ Defines the loss function used during
            training.
        """
        logits = self.predict_logits(input_data, training)
        cross_entropy_loss = tf.reduce_mean(
            tf.nn.softmax_cross_entropy_with_logits(
                labels=target,
                logits=logits))
        loss = cross_entropy_loss
        return loss

    def grads_fn(self, input_data, target):
        """ Dynamically computes the gradients of the loss value
            with respect to the parameters of the model, in each
            forward pass.
        """
        with tfe.GradientTape() as tape:
            loss = self.loss_fn(input_data, target)
        return tape.gradient(loss, self.variables)

    def fit_batch(self,
                  train_dataset,
                  test_dataset,
                  optimizer,
                  num_epochs=50,
                  verbose=50,
                  print_errors=True,
                  early_stopping_patience=0,
                  max_time=300):
        """ Function to train the model, using the selected optimizer and
            for the desired number of epochs. Uses early stopping with
            patience.
        """
        all_loss_train = []
        all_loss_test = []
        time_start = time.time()
        early_stopping_flag = False
        for epoch in range(num_epochs):
            for (input_data, target) in tfe.Iterator(
                            train_dataset.shuffle(1e8).batch(self.batch_size)):
                input_data = np.random.poisson(input_data).astype(float)
                grads = self.grads_fn(input_data, target)
                optimizer.apply_gradients(zip(grads, self.variables))
                all_loss_train.append(
                    self.loss_fn(input_data, target, training=False).numpy())
                if early_stopping_patience == 0:
                    all_loss_test.append(self.loss_fn(test_dataset[0],
                                                      test_dataset[1],
                                                      training=False).numpy())

            # Save error for early stopping
            if early_stopping_patience != 0:
                all_loss_test.append(self.loss_fn(test_dataset[0],
                                                  test_dataset[1],
                                                  training=False).numpy())
                tmp_min_test_error = all_loss_test[-1]
                if epoch == 0:
                    patience_counter = 0
                    min_test_error = tmp_min_test_error
                elif (epoch > 0) and (tmp_min_test_error < min_test_error):
                    min_test_error = tmp_min_test_error
                    patience_counter = 0
                else:
                    patience_counter += 1
                time_taken = time.time()-time_start
                if ((patience_counter >= early_stopping_patience) or
                        (time_taken > max_time)):
                    early_stopping_flag = True

            if (print_errors and
                    ((epoch == 0) | ((epoch+1) % verbose == 0))) is True:
                print('Loss at epoch %d: %3.2f %3.2f' % (epoch+1,
                                                         all_loss_train[-1],
                                                         all_loss_test[-1]))
            if early_stopping_flag is True:
                break
        return all_loss_train, all_loss_test


class cnn_model_features(object):

    def __init__(self,
                 learining_rate,
                 l2_regularization_scale,
                 dropout_probability,
                 batch_size,
                 number_filters,
                 kernel_size,
                 nodes_layer_1,
                 nodes_layer_2,
                 scaler
                 ):
        self.learining_rate = learining_rate
        self.l2_regularization_scale = l2_regularization_scale
        self.dropout_probability = dropout_probability
        self.batch_size = batch_size
        self.nodes_layer_1 = nodes_layer_1
        self.nodes_layer_2 = nodes_layer_2
        self.number_filters = number_filters
        self.kernel_size = kernel_size
        self.scaler = scaler


class filter_concat_cnn(tf.keras.Model):
    def __init__(self, model_features):
        super(cnn, self).__init__()
        """ Define here the layers used during the forward-pass
            of the neural network.
        """
        self.l2_regularization_scale = model_features.l2_regularization_scale
        dropout_probability = model_features.dropout_probability
        self.batch_size = model_features.batch_size
        self.dense_nodes = model_features.dense_nodes
        regularizer = tf.contrib.layers.l2_regularizer(
            scale=self.l2_regularization_scale)
        number_filters = model_features.number_filters
        kernel_length = model_features.kernel_length
        kernel_strides = model_features.kernel_strides
        pool_size = model_features.pool_size
        pool_strides = model_features.pool_strides
        self.scaler = model_features.scaler
        cnn_activation_function = model_features.cnn_activation_function
        dnn_activation_function = model_features.dnn_activation_function
        output_size = model_features.output_size
        cnn_trainable = model_features.cnn_trainable

        # ###################
        # ##### 1D Conv #####
        # ###################
        self.cnn_1d = {}
        for filter_index in range(len(kernel_length[0])):
            self.cnn_1d[str(filter_index)] = tf.layers.Conv1D(
                filters=number_filters[0],
                kernel_size=kernel_length[0][filter_index],
                strides=kernel_strides[0][filter_index],
                padding='same',
                activation=cnn_activation_function,
                kernel_initializer=tf.initializers.he_normal(),
                trainable=cnn_trainable)

        # ###################
        # ##### 2D Conv #####
        # ###################
        self.cnn_2d = {}
        self.cnn_2d['0'] = tf.layers.Conv2D(
            filters=number_filters[1],
            kernel_size=(kernel_length[1],
                         number_filters[0]*len(kernel_length[0])),
            strides=kernel_strides[1],
            padding='valid',
            activation=cnn_activation_function,
            kernel_initializer=tf.initializers.he_normal(),
            trainable=cnn_trainable
            )

        self.max_pooling2d = {}
        self.max_pooling2d['0'] = tf.layers.MaxPooling2D(
            pool_size=pool_size[1],
            strides=pool_strides[1],
            padding='same')

        # #################
        # ##### Dense #####
        # #################

        self.flatten = tf.layers.Flatten()

        self.dense_layers = {}
        self.dropout_layers = {}
        for layer, nodes in enumerate(self.dense_nodes):
            self.dense_layers[str(layer)] = tf.layers.Dense(
                nodes,
                activation=dnn_activation_function,
                kernel_initializer=lecun_normal(),
                kernel_regularizer=regularizer)
            self.dropout_layers[str(layer)] = tf.layers.Dropout(
                dropout_probability)
        self.output_layer = tf.layers.Dense(output_size, activation=None)

    def predict_logits(self, input_data, training=True):
        """ Runs a forward-pass through the network. Only outputs logits for
            loss function. This is because
            tf.nn.softmax_cross_entropy_with_logits calculates softmax
            internally. Note, dropout training is true here.
            Args:
                input_data: 2D tensor of shape (n_samples, n_features).
            Returns:
                logits: unnormalized predictions.
        """
        # Reshape input data
        x = self.scaler.transform(input_data)
        x = tf.reshape(x, [-1, x.shape[1], 1])
        # 1d convolutions
        x_0 = self.cnn_1d['0'](x)
        x_1 = self.cnn_1d['1'](x)
        x_2 = self.cnn_1d['2'](x)

        x = tf.concat([x_0, x_1, x_2], axis=2)
        x = tf.reshape(x, [-1,
                           x.shape[1],
                           x.shape[2],
                           1])
        # 2d convolutions
        x = self.cnn_2d['0'](x)
        x = self.max_pooling2d['0'](x)

        # dense
        x = self.flatten(x)

        for layer, nodes in enumerate(self.dense_nodes):
            x = self.dense_layers[str(layer)](x)
            x = self.dropout_layers[str(layer)](x, training)

        logits = self.output_layer(x)
        return logits

    def loss_fn(self, input_data, target, training=True):
        """ Defines the loss function used during
            training.
        """
        logits = self.predict_logits(input_data, training)
        cross_entropy_loss = tf.reduce_mean(
            tf.nn.softmax_cross_entropy_with_logits(
                labels=target,
                logits=logits))
        loss = cross_entropy_loss
        return loss

    def grads_fn(self, input_data, target):
        """ Dynamically computes the gradients of the loss value
            with respect to the parameters of the model, in each
            forward pass.
        """
        with tfe.GradientTape() as tape:
            loss = self.loss_fn(input_data, target)
        return tape.gradient(loss, self.variables)

    def fit_batch(self,
                  train_dataset,
                  test_dataset,
                  optimizer,
                  num_epochs=50,
                  verbose=50,
                  print_errors=True,
                  early_stopping_patience=0,
                  max_time=300):
        """ Function to train the model, using the selected optimizer and
            for the desired number of epochs. Uses early stopping with
            patience.
        """
        all_loss_train = []
        all_loss_test = []
        time_start = time.time()
        early_stopping_flag = False
        for epoch in range(num_epochs):
            for (input_data, target) in tfe.Iterator(
                            train_dataset.shuffle(1e8).batch(self.batch_size)):
                input_data = np.random.poisson(input_data).astype(float)
                grads = self.grads_fn(input_data, target)
                optimizer.apply_gradients(zip(grads, self.variables))
                all_loss_train.append(
                    self.loss_fn(input_data, target, training=False).numpy())
                if early_stopping_patience == 0:
                    all_loss_test.append(self.loss_fn(test_dataset[0],
                                                      test_dataset[1],
                                                      training=False).numpy())

            # Save error for early stopping
            if early_stopping_patience != 0:
                all_loss_test.append(self.loss_fn(test_dataset[0],
                                                  test_dataset[1],
                                                  training=False).numpy())
                tmp_min_test_error = all_loss_test[-1]
                if epoch == 0:
                    patience_counter = 0
                    min_test_error = tmp_min_test_error
                elif (epoch > 0) and (tmp_min_test_error < min_test_error):
                    min_test_error = tmp_min_test_error
                    patience_counter = 0
                else:
                    patience_counter += 1
                time_taken = time.time()-time_start
                if ((patience_counter >= early_stopping_patience) or
                        (time_taken > max_time)):
                    early_stopping_flag = True

            if (print_errors and
                    ((epoch == 0) | ((epoch+1) % verbose == 0))) is True:
                print('Loss at epoch %d: %3.2f %3.2f' % (epoch+1,
                                                         all_loss_train[-1],
                                                         all_loss_test[-1]))
            if early_stopping_flag is True:
                break
        return all_loss_train, all_loss_test


class filter_concat_cnn_model_features(object):

    def __init__(self,
                 learining_rate,
                 l2_regularization_scale,
                 dropout_probability,
                 batch_size,
                 output_size,
                 dense_nodes,
                 number_filters,
                 kernel_length,
                 kernel_strides,
                 pool_size,
                 pool_strides,
                 cnn_activation_function,
                 dnn_activation_function,
                 scaler,
                 cnn_trainable
                 ):
        self.learining_rate = learining_rate
        self.l2_regularization_scale = l2_regularization_scale
        self.dropout_probability = dropout_probability
        self.batch_size = batch_size
        self.output_size = output_size
        self.dense_nodes = dense_nodes
        self.number_filters = number_filters
        self.kernel_length = kernel_length
        self.kernel_strides = kernel_strides
        self.pool_size = pool_size
        self.pool_strides = pool_strides
        self.dense_nodes = dense_nodes
        self.cnn_activation_function = cnn_activation_function
        self.dnn_activation_function = dnn_activation_function
        self.scaler = scaler
        self.cnn_trainable = cnn_trainable

# ##############################################################
# ##############################################################
# #################### Training Functions ######################
# ##############################################################
# ##############################################################
# ##############################################################


def train_kfolds(training_data,
                 training_keys,
                 number_folds,
                 num_epochs,
                 model_class,
                 model_features,
                 verbose=True):

    skf = StratifiedKFold(n_splits=number_folds, shuffle=True, random_state=1)

    errors_train = []
    errors_test = []

    for train_index, test_index in skf.split(training_data, training_keys):

        # only fit scaler to training data
        model_features.scaler.fit(training_data[train_index])
        X_tensor = tf.constant(training_data[train_index])
        y_tensor = tf.constant(training_keys[train_index])
        train_dataset_tensor = tf.data.Dataset.from_tensor_slices((X_tensor,
                                                                   y_tensor))
        # not iterating through test dataset, don't need to put in TF DataSet
        test_dataset = (training_data[test_index], training_keys[test_index])

        tf.reset_default_graph()
        optimizer = tf.train.AdamOptimizer(model_features.learining_rate)
        model = model_class(model_features)
        all_loss_train, all_loss_test = model.fit_batch(train_dataset_tensor,
                                                        test_dataset,
                                                        optimizer,
                                                        num_epochs=1,
                                                        verbose=1,
                                                        print_errors=False)
        if verbose is True:
            print("training loss: {0:.2f}  testing loss: {0:.2f}".format(
                all_loss_train[-1], all_loss_test[-1]))
        errors_train.append(all_loss_train)
        errors_test.append(all_loss_test)
    if verbose is True:
        print(("final average training loss: {0:.2f} "
              "final average testing loss: {0:.2f}").format(
                    np.average(errors_train, axis=0)[-1],
                    np.average(errors_test, axis=0)[-1]))

    return np.average(errors_train, axis=0)[-1],
    np.average(errors_test, axis=0)[-1]


def train_earlystopping(training_data,
                        training_keys,
                        testing_data,
                        testing_keys,
                        model_class,
                        model_features,
                        num_epochs,
                        early_stopping_patience,
                        verbose=True,
                        fit_batch_verbose=5):

    # only fit scaler to training data
    X_tensor = tf.constant(training_data)
    y_tensor = tf.constant(training_keys)
    train_dataset_tensor = tf.data.Dataset.from_tensor_slices((X_tensor,
                                                               y_tensor))
    # not iterating through test dataset, don't need to put in TF DataSet
    test_dataset = (testing_data, testing_keys)

    tf.reset_default_graph()
    optimizer = tf.train.AdamOptimizer(model_features.learining_rate)
    model = model_class(model_features)
    all_loss_train, all_loss_test = model.fit_batch(
        train_dataset_tensor,
        test_dataset,
        optimizer,
        num_epochs=num_epochs,
        verbose=fit_batch_verbose,
        early_stopping_patience=early_stopping_patience,
        print_errors=True)
    if verbose is True:
        print("training loss: {0:.2f}  testing loss: {0:.2f}".format(
            all_loss_train[-1], all_loss_test[-1]))

    return all_loss_test


def save_model(folder_name, model_id, model, model_features):
    saver = tfe.Saver(model.variables)
    saver.save(folder_name+'/'+model_id)
    with open(folder_name+'/'+model_id+'_features', 'w') as f:
        pickle.dump(model_features, f)


def load_model(model_folder,
               model_id,
               model_class,
               training_data_length=1024,
               training_key_length=57):

    # load model features (number of layers, nodes)
    with open('./'+model_folder+'/'+model_id+'_features') as f:
        new_model_features = pickle.load(f)

    # Initialize variables by running a single training iteration
    tf.reset_default_graph()
    optimizer = tf.train.AdamOptimizer(new_model_features.learining_rate)
    model = model_class(new_model_features)

    dummy_data = np.ones([10, training_data_length])

    X_tensor = tf.constant(dummy_data)
    y_tensor = tf.constant(np.ones([10, training_key_length]))
    dummy_train_dataset = tf.data.Dataset.from_tensor_slices((X_tensor,
                                                              y_tensor))
    dummy_test_dataset = (dummy_data, np.ones([10, training_key_length]))

    _, _ = model.fit_batch(dummy_train_dataset,
                           dummy_test_dataset,
                           optimizer,
                           num_epochs=1,
                           verbose=1,
                           print_errors=False)

    # Restore saved variables
    saver = tfe.Saver(model.variables)
    saver.restore('./'+model_folder+'/'+model_id)

    return model, new_model_features.scaler


class_isotopes = ['Am241',
                  'Ba133',
                  'Co57',
                  'Co60',
                  'Cs137',
                  'Cr51',
                  'Eu152',
                  'Ga67',
                  'I123',
                  'I125',
                  'I131',
                  'In111',
                  'Ir192',
                  'U238',
                  'Lu177m',
                  'Mo99',
                  'Np237',
                  'Pd103',
                  'Pu239',
                  'Pu240',
                  'Ra226',
                  'Se75',
                  'Sm153',
                  'Tc99m',
                  'Xe133',
                  'Tl201',
                  'Tl204',
                  'U233',
                  'U235',
                  'shielded_Am241',
                  'shielded_Ba133',
                  'shielded_Co57',
                  'shielded_Co60',
                  'shielded_Cs137',
                  'shielded_Cr51',
                  'shielded_Eu152',
                  'shielded_Ga67',
                  'shielded_I123',
                  # 'shielded_I125',
                  # Removed due to max gamma energy being too weak.
                  # Any shielding fully attenuates.
                  'shielded_I131',
                  'shielded_In111',
                  'shielded_Ir192',
                  'shielded_U238',
                  'shielded_Lu177m',
                  'shielded_Mo99',
                  'shielded_Np237',
                  'shielded_Pd103',
                  'shielded_Pu239',
                  'shielded_Pu240',
                  'shielded_Ra226',
                  'shielded_Se75',
                  'shielded_Sm153',
                  'shielded_Tc99m',
                  'shielded_Xe133',
                  'shielded_Tl201',
                  'shielded_Tl204',
                  'shielded_U233',
                  'shielded_U235']
