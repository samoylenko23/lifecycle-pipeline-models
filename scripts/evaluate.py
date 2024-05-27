import json
import yaml
import os

import pandas as pd
import joblib
import numpy as np

from sklearn.model_selection import KFold, train_test_split, cross_validate
from sklearn.metrics import r2_score, mean_absolute_error

import mlflow
from dotenv import load_dotenv

TRACKING_SERVER_HOST = "127.0.0.1"
TRACKING_SERVER_PORT = 5000

EXPERIMENT_NAME = "project228_2"
RUN_NAME = 'run_baseline_project2'

load_dotenv()

mlflow.set_tracking_uri(f"http://{TRACKING_SERVER_HOST}:{TRACKING_SERVER_PORT}")
mlflow.set_registry_uri(f"http://{TRACKING_SERVER_HOST}:{TRACKING_SERVER_PORT}")


def get_params():

    with open('params.yaml', 'r') as fd:
        params = yaml.safe_load(fd)

    return params

def load_model():

    with open('models/fitted_model.pkl', 'rb') as fd:
        model = joblib.load(fd)
    
    return model

def calculate_rmse(predicted_values, true_values):
    squared_errors = (predicted_values - true_values) ** 2

    mse = np.mean(squared_errors)
    rmse = np.sqrt(mse)

    return rmse

def evaluate_model():

    params = get_params()
    data = pd.read_csv('data/datasets.csv')
    model = load_model()

    train, test = train_test_split(data,
                               shuffle=True,
                               test_size=params['test_size'],
                               random_state=params['random_state'])

    target_train = train['price']
    target_test = test['price']
    train = train.drop(['price'], axis=1)
    test = test.drop(['price'], axis=1)

    cv_strategy = KFold(n_splits=params['n_splits'])


    cv_res = cross_validate(
        model,
        train,
        target_train,
        cv=cv_strategy,
        n_jobs=params['n_jobs'],
        scoring=['neg_root_mean_squared_error', 'r2', 'neg_mean_absolute_error']
    )
    
    # Результаты с кросс-валидации
    for key, value in cv_res.items():
        cv_res[key] = round(value.mean(), 3)

    cv_res['test_rmse'] = calculate_rmse(model.predict(test), target_test)

    cv_res['test_r2'] = r2_score(model.predict(test), target_test)

    cv_res['test_mae'] = mean_absolute_error(model.predict(test), target_test)

    os.makedirs('cv_results', exist_ok=True)
    with open('cv_results/cv_res.json', 'w') as json_file:
        json.dump(cv_res, json_file)



        

    experiment = mlflow.get_experiment_by_name(EXPERIMENT_NAME)
    if experiment is None:
        experiment_id = mlflow.create_experiment(EXPERIMENT_NAME)
    else:
        experiment_id = experiment.experiment_id


    

    with mlflow.start_run(run_name=RUN_NAME, experiment_id=experiment_id) as run:
        mlflow.log_params(cv_res)
if __name__ == '__main__':
    evaluate_model()


    

