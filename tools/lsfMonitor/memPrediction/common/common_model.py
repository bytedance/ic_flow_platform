import copy
import pickle
import numpy as np
import pandas as pd
from tqdm import tqdm
from gensim.models import Word2Vec
from glove import Glove
from glove import Corpus
from sklearn.cluster import KMeans


class Word2VecModel:
    def __init__(self, sentence_col, emb_size, model_path):
        (self.sentence_col, self.emb_size, self.model_path) = (sentence_col, emb_size, model_path)
        self.feature_name = 'word2vec'
        self.feature_columns_list = ['{}_{}_{}'.format(self.feature_name, self.sentence_col, i) for i in range(self.emb_size)]

    def training_model(self, df, min_count=5, window=5):
        sentences = copy.deepcopy(df[self.sentence_col].values)

        for i in range(len(sentences)):
            sentences[i] = [str(x) for x in sentences[i]]

        w2v_model = Word2Vec(sentences, min_count=min_count, vector_size=self.emb_size, window=window)
        w2v_model.save(self.model_path)

        for i in tqdm(range(len(sentences))):
            sentences[i] = [w2v_model.wv[x] for x in sentences[i] if x in w2v_model.wv]

        emb_matrix = []

        for seq in tqdm(sentences):
            if len(seq) > 0:
                emb_matrix.append(np.mean(seq, axis=0))
            else:
                emb_matrix.append([0] * self.emb_size)

        emb_matrix = np.array(emb_matrix)
        emb_series_list = [pd.Series(emb_matrix[:, i]) for i in range(self.emb_size)]
        emb_df = pd.concat(emb_series_list, axis=1, keys=self.feature_columns_list)

        return emb_df

    def generate_word2vec_feature(self, df):
        sentences = copy.deepcopy(df[self.sentence_col].values)

        for i in range(len(sentences)):
            sentences[i] = [str(x) for x in sentences[i]]

        w2v_model = Word2Vec.load(self.model_path)

        for i in tqdm(range(len(sentences))):
            sentences[i] = [w2v_model.wv[x] for x in sentences[i] if x in w2v_model.wv]

        emb_matrix = []

        for seq in tqdm(sentences):
            if len(seq) > 0:
                emb_matrix.append(np.mean(seq, axis=0))
            else:
                emb_matrix.append([0] * self.emb_size)

        emb_matrix = np.array(emb_matrix)
        emb_series_list = [pd.Series(emb_matrix[:, i]) for i in range(self.emb_size)]
        emb_df = pd.concat(emb_series_list, axis=1, keys=self.feature_columns_list)

        return emb_df

    def kmeans_cluster(self, emb_df, save_path, n_cluster=8):
        word2vec_cluster_model = KMeans(n_clusters=n_cluster)
        emb_df = emb_df.astype('float64')
        word2vec_cluster_model.fit(emb_df)
        pickle.dump(word2vec_cluster_model, open(save_path, "wb"))

        label_df = pd.DataFrame()
        label_df[r'%s_%s_cluster_label' % (self.feature_name, self.sentence_col)] = word2vec_cluster_model.labels_

        return label_df

    def gen_cluster_label(self, emb_df, cluster_model_path):
        cluster_model = pickle.load(open(cluster_model_path, "rb"))
        emb_df = emb_df.astype('float64')
        label = cluster_model.predict(emb_df)
        label_df = pd.DataFrame()
        label_df[r'%s_%s_cluster_label' % (self.feature_name, self.sentence_col)] = label

        return label_df


class GloVeModel:
    def __init__(self, sentence_col, emb_size, corpus_path, model_path):
        (self.sentence_col, self.emb_size, self.corpus_path, self.model_path) = (sentence_col, emb_size, corpus_path, model_path)
        self.feature_name = 'glove'
        self.feature_columns_list = ['{}_{}_{}'.format(self.feature_name, self.sentence_col, i) for i in range(self.emb_size)]

    def training_model(self, df):
        sentences = copy.deepcopy(df[self.sentence_col].values)

        for i in range(len(sentences)):
            sentences[i] = [str(x) for x in sentences[i]]

        corpus_model = Corpus()
        corpus_model.fit(sentences, window=10)
        corpus_model.save(self.corpus_path)

        glove_model = Glove(no_components=self.emb_size, learning_rate=0.05, random_state=1024)
        glove_model.fit(corpus_model.matrix, epochs=10, no_threads=4, verbose=True)
        glove_model.add_dictionary(corpus_model.dictionary)
        glove_model.save(self.model_path)

        vocab = list(glove_model.dictionary.keys())

        for i in tqdm(range(len(sentences))):
            sentences[i] = [glove_model.word_vectors[glove_model.dictionary[x]] for x in sentences[i] if x in vocab]

        emb_matrix = []

        for seq in tqdm(sentences):
            if len(seq) > 0:
                emb_matrix.append(np.mean(seq, axis=0))
            else:
                emb_matrix.append([0] * self.emb_size)

        emb_matrix = np.array(emb_matrix)
        emb_series_list = [pd.Series(emb_matrix[:, i]) for i in range(self.emb_size)]
        emb_df = pd.concat(emb_series_list, axis=1, keys=self.feature_columns_list)

        return emb_df

    def generate_glove_feature(self, df):
        sentences = copy.deepcopy(df[self.sentence_col].values)

        for i in range(len(sentences)):
            sentences[i] = [str(x) for x in sentences[i]]

        self.glove_model = Glove.load(self.model_path)
        vocab = list(self.glove_model.dictionary.keys())

        for i in tqdm(range(len(sentences))):
            sentences[i] = [self.glove_model.word_vectors[self.glove_model.dictionary[x]] for x in sentences[i] if x in vocab]

        emb_matrix = []

        for seq in tqdm(sentences):
            if len(seq) > 0:
                emb_matrix.append(np.mean(seq, axis=0))
            else:
                emb_matrix.append([0] * self.emb_size)

        emb_matrix = np.array(emb_matrix)
        emb_series_list = [pd.Series(emb_matrix[:, i]) for i in range(self.emb_size)]
        emb_df = pd.concat(emb_series_list, axis=1, keys=self.feature_columns_list)

        return emb_df

    def kmeans_cluster(self, emb_df, save_path, n_cluster=8):
        glove_cluster_model = KMeans(n_clusters=n_cluster)
        emb_df = emb_df.astype('float64')
        glove_cluster_model.fit(emb_df)
        pickle.dump(glove_cluster_model, open(save_path, "wb"))

        label_df = pd.DataFrame()
        label_df[r'%s_%s_cluster_label' % (self.feature_name, self.sentence_col)] = glove_cluster_model.labels_

        return label_df

    def gen_cluster_label(self, emb_df, cluster_model_path):
        cluster_model = pickle.load(open(cluster_model_path, "rb"))
        emb_df = emb_df.astype('float64')
        label = cluster_model.predict(emb_df)
        label_df = pd.DataFrame()
        label_df[r'%s_%s_cluster_label' % (self.feature_name, self.sentence_col)] = label

        return label_df
