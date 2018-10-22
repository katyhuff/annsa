import pickle
import tensorflow as tf
import numpy as np
import tensorflow.contrib.eager as tfe
from sklearn.model_selection import KFold
from tensorflow.keras.initializers import lecun_normal


#################################################################################################################
#################################################################################################################
#########################################  Fully Connected Archetecture  ########################################
#################################################################################################################
#################################################################################################################

class dnn(tf.keras.Model):
    def __init__(self, model_features):
        super(dnn, self).__init__()
        """ Define here the layers used during the forward-pass 
            of the neural network.
        """
        l2_regularization_scale=model_features.l2_regularization_scale
        dropout_probability=model_features.dropout_probability
        nodes_layer_1=model_features.nodes_layer_1
        nodes_layer_2=model_features.nodes_layer_2      
        
        # define l2 regularization
        self.regularizer = tf.keras.regularizers.l2(l=l2_regularization_scale)        
        # Hidden layer.
        self.dense_layer1 = tf.layers.Dense(nodes_layer_1, 
                                            activation=tf.nn.relu,
                                            #kernel_initializer=tf.truncated_normal_initializer(stddev = 1/np.sqrt(1024)),
                                            kernel_initializer=lecun_normal(),
                                            kernel_regularizer=self.regularizer)
        self.drop1 = tf.layers.Dropout(dropout_probability)
        self.dense_layer2 = tf.layers.Dense(nodes_layer_2,
                                            activation=tf.nn.relu,
                                            #kernel_initializer=tf.truncated_normal_initializer(stddev = 1/np.sqrt(nodes_layer_1)),
                                            kernel_initializer=lecun_normal(),
                                            kernel_regularizer=self.regularizer)
        self.drop2 = tf.layers.Dropout(dropout_probability)
        # Output layer. No activation.
        self.output_layer = tf.layers.Dense(57, activation=None)
        
    def predict_logits(self, input_data, training=True):
        """ Runs a forward-pass through the network. Only outputs logits for loss function. 
            This is because tf.nn.softmax_cross_entropy_with_logits calculates softmax internally.   
            Note, dropout training is true here.
            Args:
                input_data: 2D tensor of shape (n_samples, n_features).   
            Returns:
                logits: unnormalized predictions.
        """
        # Reshape input data
        x=tf.reshape(input_data,[-1,1,1024])
        x=self.dense_layer1(x)
        x=self.drop1(x,training)
        x=self.dense_layer2(x)
        x=self.drop2(x,training)
        logits=self.output_layer(x)
        
        return logits
    
    def predict(self, input_data, training=False):
        """ Runs a forward-pass through the network and uses softmax output. Dropout training is off, this is 
            not used for gradient calculations in loss function.
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
        cross_entropy_loss = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(labels=target, logits=logits))
        l2_weights = [self.weights[i] for i in range(len(self.weights)) if i%2==0]
        l2_loss = tf.contrib.layers.apply_regularization(self.regularizer, l2_weights)
        loss = cross_entropy_loss+l2_loss
        return loss
    
    def grads_fn(self, input_data, target):
        """ Dynamically computes the gradients of the loss value
            with respect to the parameters of the model, in each
            forward pass.
        """
        with tfe.GradientTape() as tape:
            loss = self.loss_fn(input_data, target) 
        return tape.gradient(loss, self.variables)
    
    def fit(self, input_data, target, optimizer, num_epochs=500, verbose=50):
        """ Function to train the model, using the selected optimizer and
            for the desired number of epochs.
        """
        for i in range(num_epochs):
            grads = self.grads_fn(input_data, target)
            optimizer.apply_gradients(zip(grads, self.variables))
            if (i==0) | ((i+1)%verbose==0):
                print('Loss at epoch %d: %f' %(i+1, self.loss_fn(input_data, target, training=False).numpy()))
                
    
    def fit_batch(self, train_dataset,test_dataset, optimizer, num_epochs=50, verbose=50, print_errors=True):
        """ Function to train the model, using the selected optimizer and
            for the desired number of epochs.
        """
        all_loss_train=[]
        all_loss_test=[0]
        for i in range(num_epochs):
            for (input_data, target) in tfe.Iterator(train_dataset.shuffle(1e8).batch(512)):
                grads = self.grads_fn(input_data, target)
                optimizer.apply_gradients(zip(grads, self.variables))
                all_loss_train.append(self.loss_fn(input_data, target, training=False).numpy())
                all_loss_test.append(self.loss_fn(test_dataset[0],test_dataset[1], training=False).numpy())
            if print_errors==True and ((i==0) | ((i+1)%verbose==0)):
                print('Loss at epoch %d: %3.2f %3.2f' %(i+1, np.average(all_loss_train[-10:]), np.average(all_loss_test[-10:])))
        return all_loss_train, all_loss_test
    
    
    
class dnn_model_features(object):
    
    def __init__(self,learining_rate,
                      l2_regularization_scale,
                      dropout_probability,
                      nodes_layer_1,
                      nodes_layer_2,
                      scaler
                ):
        self.learining_rate=learining_rate
        self.l2_regularization_scale=l2_regularization_scale
        self.dropout_probability=dropout_probability
        self.nodes_layer_1=nodes_layer_1
        self.nodes_layer_2=nodes_layer_2
        self.scaler=scaler
        
        
#################################################################################################################
#################################################################################################################
#########################################  Convolutional Archetecture  ##########################################
#################################################################################################################
#################################################################################################################
class cnn(tf.keras.Model):
    def __init__(self, model_features):
        super(cnn, self).__init__()
        """ Define here the layers used during the forward-pass 
            of the neural network.
        """
        l2_regularization_scale=model_features.l2_regularization_scale
        dropout_probability=model_features.dropout_probability
        nodes_layer_1=model_features.nodes_layer_1
        nodes_layer_2=model_features.nodes_layer_2  
        input_shape=(-1,1024,1)
        cnn_filters=(3, 9)
        cnn_kernel=(20, 55)
        fc_units=256
              
        # Convolution layers.
        self.cnn_layer1=tf.layers.Conv1D(filters=cnn_filters[0],
                                 kernel_size=cnn_kernel[0],
                                 strides=1,
                                 padding='valid',
                                 activation='relu')
        self.max_pool1=tf.layers.MaxPooling1D(pool_size=2, strides=2, padding='valid')
        self.cnn_layer2=tf.layers.Conv1D(filters=cnn_filters[1],
                               kernel_size=cnn_kernel[1],
                               strides=1,
                               padding='valid',
                               activation='relu')
        self.max_pool2=tf.layers.MaxPooling1D(pool_size=2, strides=2, padding='valid')
        
        # Fully connected layers.
        self.flatten1=tf.layers.Flatten()
        self.dropout1=tf.layers.Dropout(dropout_probability)
        self.dense_layer1 = tf.layers.Dense(nodes_layer_1,
                                            #kernel_initializer=lecun_normal(),
                                            activation=tf.nn.softsign)
        self.dropout2=tf.layers.Dropout(dropout_probability)
        self.output_layer = tf.layers.Dense(57,
                                            #kernel_initializer=lecun_normal(),
                                            activation=None)
        
    def predict_logits(self, input_data, training=True):
        """ Runs a forward-pass through the network. Only outputs logits for loss function. 
            This is because tf.nn.softmax_cross_entropy_with_logits calculates softmax internally.   
            Note, dropout training is true here.
            Args:
                input_data: 2D tensor of shape (n_samples, n_features).   
            Returns:
                logits: unnormalized predictions.
        """
        # Reshape input data
        x=tf.reshape(input_data,[-1,1024,1])
        x=self.cnn_layer1(x)
        x=self.max_pool1(x)
        x=self.cnn_layer2(x)
        x=self.max_pool2(x)
        x=self.flatten1(x)
        x=self.dropout1(x)
        x=self.dense_layer1(x)
        x=self.dropout2(x)
        logits=self.output_layer(x)        
        return logits
    
    def predict(self, input_data, training=False):
        """ Runs a forward-pass through the network and uses softmax output. Dropout training is off, this is 
            not used for gradient calculations in loss function.
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
        cross_entropy_loss = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(labels=target, logits=logits))
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
    
    def fit(self, input_data, target, optimizer, num_epochs=500, verbose=50):
        """ Function to train the model, using the selected optimizer and
            for the desired number of epochs.
        """
        for i in range(num_epochs):
            grads = self.grads_fn(input_data, target)
            optimizer.apply_gradients(zip(grads, self.variables))
            if (i==0) | ((i+1)%verbose==0):
                print('Loss at epoch %d: %f' %(i+1, self.loss_fn(input_data, target, training=False).numpy()))
                
    
    def fit_batch(self, train_dataset,test_dataset, optimizer, num_epochs=50, verbose=50, print_errors=True):
        """ Function to train the model, using the selected optimizer and
            for the desired number of epochs.
        """
        all_loss_train=[]
        all_loss_test=[0]
        for i in range(num_epochs):
            for (input_data, target) in tfe.Iterator(train_dataset.shuffle(1e8).batch(512)):
                grads = self.grads_fn(input_data, target)
                optimizer.apply_gradients(zip(grads, self.variables))
                all_loss_train.append(self.loss_fn(input_data, target, training=False).numpy())
                all_loss_test.append(self.loss_fn(test_dataset[0],test_dataset[1], training=False).numpy())
            if print_errors==True and ((i==0) | ((i+1)%verbose==0)):
                print('Loss at epoch %d: %3.2f %3.2f' %(i+1, np.average(all_loss_train[-10:]), np.average(all_loss_test[-10:])))
        return all_loss_train, all_loss_test
    
    
    
class cnn_model_features(object):
    
    def __init__(self,learining_rate,
                      l2_regularization_scale,
                      dropout_probability,
                      nodes_layer_1,
                      nodes_layer_2,
                      scaler
                ):
        self.learining_rate=learining_rate
        self.l2_regularization_scale=l2_regularization_scale
        self.dropout_probability=dropout_probability
        self.nodes_layer_1=nodes_layer_1
        self.nodes_layer_2=nodes_layer_2
        self.scaler=scaler
        
        
##################################################################################################################
##################################################################################################################
#############################################  Training Functions  ###############################################
##################################################################################################################
##################################################################################################################
        
        
        
def train_kfolds(training_data,
                 training_keys,
                 number_folds,
                 num_epochs,
                 model_class,
                 model_features,
                 verbose=True):

    kf = KFold(n_splits=number_folds,shuffle=False,random_state=1)
    kf_split_indicies=kf.split(training_data)
    
    kf_errors_train=[]
    kf_errors_test=[]

    for train_index, test_index in kf.split(training_data):
        
        training_data_scaled=model_features.scaler.fit_transform(training_data[train_index])
        testing_data_scaled=model_features.scaler.transform(training_data[test_index])
        
        X_tensor = tf.constant(training_data_scaled)
        y_tensor = tf.constant(training_keys[train_index])
        train_dataset_tensor = tf.data.Dataset.from_tensor_slices((X_tensor, y_tensor))
        # not iterating through test dataset, don't need to put in TF DataSet
        test_dataset = (testing_data_scaled, training_keys[test_index])

        tf.reset_default_graph()
        optimizer = tf.train.AdamOptimizer(model_features.learining_rate)
        model = model_class(model_features)
        all_loss_train, all_loss_test = model.fit_batch(train_dataset_tensor,
                                                        test_dataset,
                                                        optimizer,
                                                        num_epochs=1,
                                                        verbose=1,
                                                        print_errors=False)
        if verbose==True:
            print ("training loss: {0:.2f}  testing loss: {0:.2f}".format(all_loss_train[-1],all_loss_test[-1]))
        kf_errors_train.append(all_loss_train)
        kf_errors_test.append(all_loss_test)
    if verbose==True:
        print ("final average training loss: {0:.2f} final average testing loss: {0:.2f}".format(np.average(kf_errors_train,axis=0)[-1],
                                                                                             np.average(kf_errors_test,axis=0)[-1]))
        
    return np.average(kf_errors_train,axis=0)[-1],np.average(kf_errors_test,axis=0)[-1] 
    
def save_model(model_id,model,model_features):
    saver = tfe.Saver(model.variables)
    saver.save('./model_checkpoints/'+model_id)
    with open('./model_checkpoints/'+model_id+'_features', 'w') as f:
        pickle.dump(model_features,f)
        
class_isotopes=['Am241',
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
                 'shileded_Am241',
                 'shileded_Ba133',
                 'shileded_Co57',
                 'shileded_Co60',
                 'shileded_Cs137',
                 'shileded_Cr51',
                 'shileded_Eu152',
                 'shileded_Ga67',
                 'shileded_I123',
                 #'shileded_I125', # Removed due to max gamma energy being too weak. Any shielding fully attenuates.
                 'shileded_I131',
                 'shileded_In111',
                 'shileded_Ir192',
                 'shileded_U238',
                 'shileded_Lu177m',
                 'shileded_Mo99',
                 'shileded_Np237',
                 'shileded_Pd103',
                 'shileded_Pu239',
                 'shileded_Pu240',
                 'shileded_Ra226',
                 'shileded_Se75',
                 'shileded_Sm153',
                 'shileded_Tc99m',
                 'shileded_Xe133',
                 'shileded_Tl201',
                 'shileded_Tl204',
                 'shileded_U233',
                 'shileded_U235']
        
        
        
        
        
        
        
        
        
        
        
        
        
        