import pandas as pd
import numpy as np
import pyspark as ps
from pyspark.sql import SparkSession
from pyspark.sql.functions import udf
import psycopg2
from pyspark.ml.recommendation import ALS
from pandas.io import sql
from pyspark.ml.evaluation import RegressionEvaluator
from itertools import product

class SongRecommender():

    def __init__(self,
                itemCol='song_id',
                userCol='sampled_by_song_id',
                ratingCol='is_connected',
                nonnegative=True,
                regParam=0.01,
                rank=10,
                alpha=1,
                implicitPrefs=True):

        self.itemCol = itemCol
        self.userCol = userCol
        self.ratingCol = ratingCol
        self.nonnegative = nonnegative
        self.regParam = regParam
        self.rank = rank
        self.alpha = alpha
        self.implicitPrefs = implicitPrefs
        self.als_model = ALS(itemCol=self.itemCol,
                            userCol=self.userCol,
                            ratingCol=self.ratingCol,
                            nonnegative=self.nonnegative,
                            regParam=self.regParam,
                            rank=self.rank,
                            alpha=self.alpha,
                            implicitPrefs=self.implicitPrefs)

        self.spark = (ps.sql.SparkSession.builder 
                        .master("local[4]") 
                        .appName("afternoon sprint") 
                        .getOrCreate()
                        )
        
    
    def fit(self, X):
        return self.als_model.fit(X)
         

    def transform(self, recommender, X):
        return recommender.transform(X)


    def rmse(self, predictions, has_nan_values=False):
        evaluator = RegressionEvaluator(metricName='rmse', 
                                       labelCol=self.ratingCol,
                                       predictionCol='prediction')
        if has_nan_values:
            # check for nan values by computation
            filtered_preds = predictions.filter("prediction + 1 > prediction")
            return evaluator.evaluate(filtered_preds)
        
        else:
            return evaluator.evaluate(predictions)

    def generate_negative_targets(self, X, col1, col2,
                                  target_col, n_new_combos=None,
                                  get_all=False, seed=216):
        '''
        Generates new id combinations to get data with a negative target in order to
        help with model evaluation

        Parameters
        ----------
        col1 : string, name of column 1
        col2 : string, name of columns 2
        X : spark df with all possible values for col1 and col2 where target = 1

        Returns
        -------
        X_with_negative_targets : spark dataframe with new combos where target = 0
        '''
        df = X.toPandas()

        col1_uniques = df[col1].unique()
        col2_uniques = df[col2].unique()

        if get_all:
            counter = 0
            existing_combos = set((x,y) for [x,y] in df[[col1, col2]].values)
            df_size = len(df)
            while counter < df_size:
                if df_size - counter >= 500:
                    new_combos = set((x,y) for (x,y) in 
                                product(col1_uniques[counter:counter+500],
                                        col2_uniques))
                else:
                    new_combos = set((x,y) for (x,y) in 
                                product(col1_uniques[counter:],
                                        col2_uniques))


                difference = (existing_combos - new_combos)
                difference_with_target = [combo + (0,) for combo in difference]
                negative_target_df = pd.DataFrame(difference_with_target,
                                         columns=[col1, col2, target_col])
                df = pd.concat([df, negative_target_df], sort=True)
                df.reset_index()
                counter += 500
                print(counter)
        else:
            if n_new_combos is None:
                n_new_combos = len(df)

            new_combos = []
            while len(new_combos) < n_new_combos:
                val1 = np.random.choice(col1_uniques)
                val2 = np.random.choice(col2_uniques)
                # print(f'trying {(val1, val2)}')
                if len(df.loc[(df[col1] == val1) & (df[col2] == val2)]) == 0:
                    new_combos.append((val1, val2))
            negative_target_df = pd.DataFrame(new_combos, columns=[col1, col2])
            negative_target_df[target_col] = 0
            df = pd.concat([df, negative_target_df], sort=True).reset_index()
        return self.spark.createDataFrame(df)

    def get_predictions_for_song(self, recommender, dataset, song_id, n_predictions=10):
        '''
        Parameters
        ----------
        recommender : a fit ALS model
        dataset : full training set 
        X : spark df with all possible values for col1 and col2 where target = 1

        Returns
        -------
        dataframe : top 10 recommendations for song
        '''
        one_rec = recommender.recommendForUserSubset(
            dataset.filter('sampled_by_song_id = %s' % song_id), 2*n_predictions)
        df = one_rec.toPandas()
        song_id_list = list([song_id] * 10)
        song_id_df = pd.DataFrame(song_id_list, columns=['sampled_by_song_id'])
        recs_df = pd.DataFrame(df.loc[0,'recommendations'],
                        columns=['song_id', 'rating'])
        return song_id_df.merge(recs_df, left_index=True, right_index=True)
    

    def get_predictions_for_all_users(self, X, recommender, n_predictions=10):
        if type(X) != pd.core.frame.DataFrame:
            existing_pairs_df = X.toPandas()
            existing_pairs = set((x,y) for [x,y] in 
                            existing_pairs_df.loc[:,['song_id', 'sampled_by_song_id']].values)
        else:
            existing_pairs = set((x,y) for [x,y] in 
                            X.loc[:,['song_id', 'sampled_by_song_id']].values)

        recs = recommender.recommendForAllUsers(n_predictions * 10)
        recs_df = recs.toPandas()
        
        output = pd.DataFrame(columns=['user_song_id', 'item_song_id', 'rating'])
        for row in recs_df.itertuples():
            if row[0] % 10000 == 0:
                print(row[0])
            df = pd.DataFrame(row[2], columns=['item_song_id', 'rating'])
            df['user_song_id'] = list([row[1]] * (n_predictions * 10))
            rows_to_drop = []
            for entry in df.itertuples():
                if (entry[3], entry[1]) in existing_pairs:
                    rows_to_drop.append(entry[0])
            df.drop(rows_to_drop, axis=0, inplace=True)
            output = pd.concat([output, df[:n_predictions]], sort=True)
            

        return output.loc[:,['user_song_id', 'item_song_id', 'rating']]












