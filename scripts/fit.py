import yaml
import os
import joblib

import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from category_encoders import CatBoostEncoder
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.tree import DecisionTreeRegressor
from sklearn.model_selection import train_test_split
import mlflow
from dotenv import load_dotenv

TRACKING_SERVER_HOST = "127.0.0.1"
TRACKING_SERVER_PORT = 5000

EXPERIMENT_NAME = "ALEXEY_PROJECT"
RUN_NAME = 'baseline_model_dvc_project2'
REGISTRY_MODEL_NAME = 'baseline_model_dvc'

load_dotenv()

mlflow.set_tracking_uri(f"http://{TRACKING_SERVER_HOST}:{TRACKING_SERVER_PORT}")
mlflow.set_registry_uri(f"http://{TRACKING_SERVER_HOST}:{TRACKING_SERVER_PORT}")

def get_params():

    with open('params.yaml') as fd:
        params = yaml.safe_load(fd)
    
    return params



def fit_model():

    experiment = mlflow.get_experiment_by_name(EXPERIMENT_NAME)
    if experiment is None:
        experiment_id = mlflow.create_experiment(EXPERIMENT_NAME)
    else:
        experiment_id = experiment.experiment_id

    params = get_params()

    data = pd.read_csv('data/datasets.csv')

    train, _ = train_test_split(data,
                               shuffle=True,
                               test_size=params['test_size'],
                               random_state=params['random_state'])

    target = train['price']
    X_train = train.drop(['price'], axis=1)

    cat_features = X_train.select_dtypes(include='object')
    potential_binary_features = cat_features.nunique() == 2

    binary_cat_features = cat_features[potential_binary_features[potential_binary_features].index]
    other_cat_features = cat_features[potential_binary_features[~potential_binary_features].index]
    num_features = X_train.select_dtypes(['float', 'int'])


    preprocessor = ColumnTransformer(
        [
            ('binary', OneHotEncoder(drop=params['ohe_drop']), binary_cat_features.columns.tolist()),
            ('cat', CatBoostEncoder(return_df=False), other_cat_features.columns.tolist()),
            ('num', StandardScaler(), num_features.columns.tolist())
        ],
        remainder=params['remainder'],
        verbose_feature_names_out=params['verbose_feature_names_out']
    )

    model = DecisionTreeRegressor(max_depth=params['max_depth'], random_state=params['random_state'])

    pipeline = Pipeline(
        [
            ('preprocessor', preprocessor),
            ('model', model)
        ]
    )
    pipeline.fit(X_train, target)

    # Сохраним модель локально
    os.makedirs('models', exist_ok=True)
    with open('models/fitted_model.pkl', 'wb') as fd:
        joblib.dump(pipeline, fd)

    # Залогируем модель в mlflow
    pip_requirements = "../requirements.txt"
    signature = mlflow.models.infer_signature(X_train, target)
    input_example = X_train[:10]
    metadata = {"target_name": "price"}


    with mlflow.start_run(run_name=RUN_NAME, experiment_id=experiment_id) as run:
        model_info = mlflow.sklearn.log_model(
            sk_model=pipeline,
            artifact_path="models",
            registered_model_name=REGISTRY_MODEL_NAME,
            signature=signature,
            pip_requirements=pip_requirements,
            input_example=input_example,
            metadata=metadata
    )
        mlflow.log_params(pipeline.get_params())


if __name__ == '__main__':
	fit_model()