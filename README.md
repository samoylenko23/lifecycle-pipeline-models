**Привет! Меня зовут Алексей! Хотел бы отметить, что sbs я не перезапускал в тетради, потому что нереально было ждать каждый час на отборе признаков. Поскольк прерывание ядра работает странно и не получается остановить одну ячейку и приходится перезапускать весь ноутбук заново... Optuna тоже странно работает на таком маленьком количестве параметров, не понимаю почему.**






# Полный Pipeline разработки ML

Добро пожаловать в репозиторий демонстрации полного pipeline разработки ml, начиная с этапа выгрузки данных с БД при помощи AirFlow, обучение и логирование baseline модели в DVC, заканчивая Feature Engineering, Feature Selection, подбор лучших гиперпараметров и логирование результатов и моделей для прода и отслеживания.

Разберем это на примере улучшения ключевых метрик модели для предсказания стоимости квартир Яндекс Недвижимости.


**Краткий Pipeline проекта**:

0. Анализ бизнес-задачи и перевод в задачу ML
1. Настройка виртуального окружения проекта
2. Развертывание AirFlow + TelegramBot для сообщений по окончании DAG
3. Развертывание DVC
4. Развертывание MLflow (Server + Model Registry)
5. Написание DAG для первичной выгрузки данных
6. Написание DAG для первичной предобработки данных
7. Краткий EDA и предобработка для Baseline
8. Написание pipeline DVC для разработки baseline
9. Логирование первичных результатов и модели baseline в Mlflow
10. Глубокий EDA + логирование артефактов в MLflow
11. Feature Engineering и обучение модели, логирование новой модели. Применение различных техник расширения признакового пространства (preprocessing, autofeat).
12. Feature Selection (mlxtend) и обучение новой модели, логирование артефактов.
13. Подбор гиперпараметров Optuna + логирование подбора и моделей. Визуализация подбора гиперпараметров.
14. Результаты экспериментов


**Используемые инструменты**: PostgreSQL, AirFlow, DVC, MLflow, Optuna, Autofeat, mlxtend, Docker, Pandas, Scikit-learn, CatBoost

**Бакет**: s3-student-mle-20240326-443674cadb


## Клонирование репозитория и установка зависимостей:

* git clone https://github.com/samoylenko23/mle-pipeline-model-development.git
* cd mle-pipeline-model-development
* python3 -m venv myenv
* source myenv/bin/activate
* pip install -r requirements.txt


# Развертывание MLflow:

Развертывание Mlflow, при поднятом Postgres и использовании S3. Удалённые хранилища для экспериментов и артефактов с локальным Tracking Server:
1. В .env прописываем креды для доступа:
AWS:
    * MLFLOW_S3_ENDPOINT_URL
    * AWS_ACCESS_KEY_ID
    * AWS_SECRET_ACCESS_KEY
    * AWS_BUCKET_NAME
Затем для Postgres:
    * DB_DESTINATION_USER
    * DB_DESTINATION_PASSWORD
    * DB_DESTINATION_HOST
    * DB_DESTINATION_PORT
    * DB_DESTINATION_NAME

2. Считываем креды в переменные окружения:
    * export $(cat .env | xargs)

3. Устанавливаем mlflow:
    * pip install mlflow==2.7.1 

4. Обратите внимание, что для работы с базой данных Postgresql вам понадобится библиотека psycopg. Установить ее можно с помощью такой команды:
    * pip install psycopg && pip install 'psycopg[binary]'

5. Создайте новый файл run_mlflow_server.sh для локального запуска Tracking Server с удалённой базой данных PostgreSQL и удалённым объектным хранилищем Object Storage в Yandex Cloud:

6. Далее в скрипте прописываем:
```
export MLFLOW_S3_ENDPOINT_URL=https://storage.yandexcloud.net
export AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID
export AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY
export AWS_BUCKET_NAME=$S3_BUCKET_NAME

echo "MLFLOW_S3_ENDPOINT_URL: $MLFLOW_S3_ENDPOINT_URL"
echo "AWS_ACCESS_KEY_ID: $AWS_ACCESS_KEY_ID"
echo "AWS_SECRET_ACCESS_KEY: $AWS_SECRET_ACCESS_KEY"
echo "AWS_BUCKET_NAME: $AWS_BUCKET_NAME"
   

mlflow server \
  --registry-store-uri postgresql://$DB_DESTINATION_USER:$DB_DESTINATION_PASSWORD@$DB_DESTINATION_HOST:$DB_DESTINATION_PORT/$DB_DESTINATION_NAME\
  --backend-store-uri postgresql://$DB_DESTINATION_USER:$DB_DESTINATION_PASSWORD@$DB_DESTINATION_HOST:$DB_DESTINATION_PORT/$DB_DESTINATION_NAME\
  --default-artifact-root s3://$AWS_BUCKET_NAME \
  --no-serve-artifacts
  ```

7. Запускаем mlflow:
    * sh run_mlflow_server.sh 

# Развертывание Airflow в Docker:

1. Находясь в папке проекта, запустите команду ниже в терминале. В результате в папке проекта должен появиться файл docker-compose.yaml:

    * curl -LfO https://airflow.apache.org/docs/apache-airflow/2.7.3/docker-compose.yaml 


2. Пишем свой Dockerfile:
```
FROM apache/airflow:2.7.3-python3.10 
COPY ./requirements.txt ./tmp/requirements.txt
COPY .env .env
RUN pip install -U pip
RUN pip install -r ./tmp/requirements.txt
ENV PYTHONPATH="${PYTHONPATH}:/home/mle-user/mle-pipeline-model-development/airflow"
```
3. Разрешаем расширения исходных образов в файле docker-compose.yaml:

По инструкции от разработчиков Airflow достаточно убрать комментарий (знак #) в строке под номером 54 файла docker-compose.yaml. В ней должно быть написано: build: .. А строку 53, наоборот, нужно закомментировать. Такая запись будет знаком для Docker Compose, что при запуске контейнера нужно использовать кастомное расширение, которые описали в Dockerfile. 

4. Инициализация AirFlow

Создаем папки для всех DAG, плагинов, логов и конфигураций — они будут использоваться в работе Airflow:

    * mkdir -p ./dags ./logs ./plugins ./config 

Сохраните ваш AIRFLOW_UID для виртуальной машины в файл .env. Это необходимо для корректной работы Airflow при запуске на Linux:

    * echo -e "\nAIRFLOW_UID=$(id -u)" >> .env 


Затем запустите команду, которая создаст учётную запись с логином и паролем Airflow для веб-интерфейса:

    * docker compose up airflow-init 


Второй командой разработчики Airflow советуют очистить возможный кэш, который появился в результате первого шага. Если этого не сделать, то могут возникнуть непредвиденные ошибки:

    * docker compose down --volumes --remove-orphans 


5. Запускаем контейнер:
    * docker compose up --build 

6. Если нужно временно остановить работы AirFlow:
    * docker compose down 



# Развертывание DVC:

1. DVC, как и любая другая библиотека, устанавливается через pip:

    * pip install dvc

2. Инициализируйте DVC в репозитории — это нужно делать только при настройке, чтобы запустить DVC:

    * dvc init

3. В результате появится папка .dvc — в ней хранятся настройки DVC, которые нужны для исполнения команд. Затем соедините DVC с облачным хранилищем, выполнив четыре последовательные команды:

Добавьте с помощью add облачное хранилище s3://S3_BUCKET_NAME в качестве удалённого хранилища DVC. Настройте его использование по умолчанию флагом -d и дайте название. Например, my_storage.

На место S3_BUCKET_NAME вставьте полученное хранилище:

    * dvc remote add -d my_storage s3://S3_BUCKET_NAME 

Измените параметр endpointurl, в котором содержится ссылка на фактическое расположение хранилища my_storage, с помощью remote modify. Хранилище находится в Yandex Cloud, поэтому ссылка имеет вид: https://storage.yandexcloud.net:

    * dvc remote modify my_storage endpointurl \
                                        https://storage.yandexcloud.net 


Модифицируйте параметр credentialpath — то есть путь до файла с логином и паролем к хранилищу my_storage. Они должны находиться в файле .env. Флаг —local означает, что эти изменения должны быть невидимы для Git:

    * dvc remote modify --local my_storage credentialpath '.env' 

Разрешите версионирование для этого хранилища — это нужно, чтобы файлы в хранилище сохранялись в читабельной форме.

    * dvc remote modify my_storage version_aware true 


Проверьте, что DVC успешно подключён к удалённому хранилищу:
    * dvc remote list
    * dvc pull 

4. Также после 3 этапа может быть полезным инициализировать в директории .dvc файл config.local. Это поможет избежать дополнительных проблем:
```
   ['remote "my_storage"']
       url = s3://s3-student-f34f3g34g34g
       endpointurl = https://storage.yandexcloud.net
       version_aware = true
       access_key_id = YXXXXXXXXXXXXXXXXX
       secret_access_key = YXXXXXXXXXXXXXXXXXXXXXXXXXXrj   
```


# Описание шагов проекта:

**Анализ бизнес-задачи и перевод в задачу ML**: 

Мы работаем в Яндекс Недвижимости, маркетплейсе для аренды и покупки жилой и коммерческой недвижимости. Наша задача — выступить надёжным посредником между арендодателями или продавцами и потенциальными арендаторами или покупателями, сделав процесс сделки максимально эффективным и безопасным для обеих сторон.

Стоимость объекта недвижимости можно объективно оценить извне — это устранит разногласия между сторонами и увеличит среднемесячное количество сделок на платформе.

 Мы разработали базовое решение в виде модели машинного обучения, а также организовали пайплайн данных в Airflow + DVC. Менеджеры убедились, что модель с точки зрения бизнеса потенциально прибыльна, однако вместе с тем сделали вывод, что метрики модели можно улучшить. Этим в этом проекте мы и займемся.


**Настройка виртуального окружения проекта**:
    * Настроено выше

**Развертывание AirFlow**:
    * Настроено выше


**Развертывание DVC**:
    * Настроено выше


**Развертывание MLflow (Server + Model Registry):**
    * Настроено выше. 


Написание DAG + отправка сообщений в телеграмме в телеграмм бот по окончании работы DAG:

    - dags:
        - /dags/bulding.py
            Функции:
                - create_table
                - extract
                - transform
                - load
        - dags/clean_bulding.py
                Функции:
                - create_table
                - extract
                - transform
                - load

    - plugins:
        - /plugins/messages.py

    В первом DAG prepare_building_datasets в файле bulding происходит первичная загрузка и объединение таблиц. В transform происходит создание нового id, совмещающего номер дома и квартиры. А также удалены супер-огромные цены на дом.

    Во втором DAG clean_building_datasets в файле clean_bulding_datasets происходит загрузка данных из старой обработанной таблицы. Создание новой таблицы, учитывая удаленные столбцы. Затем в transform происходит удаление явных дубликатов, их не нашлось, удаление выбросов, а также удаление пропусков (их тоже не нашлось). И в конце загружаю данные в новую таблицу clean_dataset_build_price_2

**Написание pipeline DVC для разработки baseline + логирование в MLflow:**


    - scripts:
        - /scripts/data.py
            Функции:
                - load_data
                - prepare_data
        -scripts/fit.py
                Функции:
                - get_params
                - fit_model
        - /scripts/evaluate.py
                Функции:
                - get_params
                - load_model
                - calculate_rmse
                - evaluate_model

    - dvc.lock:
        - /dvc.lock
    
    - dvc.yaml:
        - /dvc.yaml
    
    - params.yaml:
        - /params.yaml


    В шаге data.py происходит загрузка данных из предобработанного датасета из БД таблицы с именем clean_dataset_build_price_2.

    В шаге fit.py происходит разбивка на train и test, причем test пока опускаем, обучение только на train. Дропаем ненужные столбцы. Затем проводим простейшую предобработку и обучаем DecisionTreeRegressor. Логируем модель и гиперпараметры в MLflow.

    В шаге evaluate.py происходит оценка на кросс-валидации со стратегией K-Fold на train и запись результатов в словарь, также отдельно проверяем метрики на test и данные также заносим в словарь. Логируем в Mlflow.
 
# Работа в .ipynb. Далее основная работа идет в PROJECT.ipynb
**Логирование первичных результатов и модели baseline в Mlflow:**


    В ноутбуке будем вести таблицу для результатов улучшения модели. Сначала извлечем через MLFLOW API результаты с DVC:

Инициализируем client API:
```
client = mlflow.MlflowClient(tracking_uri=f"http://{TRACKING_SERVER_HOST}:{TRACKING_SERVER_PORT}",
                             registry_uri=f"http://{TRACKING_SERVER_HOST}:{TRACKING_SERVER_PORT}")
```
Считываем данные:

```
result_baseline = client.get_run(run_id='6aee201f20bc4fceaa3a28066ac06a5d').data.params
result_baseline
```

Получаем уникальный номер эксперимента по имени:
```
experiment_id = client.get_experiment_by_name(EXPERIMENT_NAME).experiment_id
```


Извлекаем данные из БД для дальнейшем работы:

```
load_dotenv()

connection = {"host": os.getenv("DB_DESTINATION_HOST"),
              'port': os.getenv("DB_DESTINATION_PORT"),
              "dbname": os.getenv("DB_DESTINATION_NAME"),
              "user": os.getenv("DB_DESTINATION_USER"),
              "password": os.getenv("DB_DESTINATION_PASSWORD"),
              'sslmode': 'require',
              'target_session_attrs': 'read-write'}

TABLE_NAME = 'clean_dataset_build_price_2'

with psycopg.connect(**connection) as conn:
    with conn.cursor() as cur:
        cur.execute(f'SELECT * FROM {TABLE_NAME}')
        data = cur.fetchall()
        columns = [col[0] for col in cur.description]

data = pd.DataFrame(data, columns=columns)

```

**Глубокий EDA + логирование артефактов в MLflow:**

Подробнее с EDA в тетради. Логируем результаты.

**Feature Engineering и обучение модели, логирование новой модели. Применение различных техник расширения признакового пространства (preprocessing + pipeline, autofeat):**

Для sklearn Feature Engineering буду использовать фичи:
* kitchen_area
* living_area
* total_area
* house_age
* ceiling_height

Для них использую PolynomialFeatures, KBinsDiscretizer и SplineTransformer


Если у нас есть 5 исходных признаков: kitchen_area, living_area, total_area, и house_age, ceiling_height то полиномиальные признаки второй степени будут включать:
- Все исходные признаки (1 степень): kitchen_area, living_area, total_area, house_age, ceiling_height
- Квадраты каждого признака (2 степень): kitchen_area^2, living_area^2, total_area^2, house_age^2, ceiling_height^2
- Все возможные пары взаимодействий (произведения признаков): kitchen_area \* living_area, kitchen_area \* total_area, и т.д.


KBinsDiscretizer делит каждый числовой признак на несколько интервалов (бинов). В вашем случае используется параметр n_bins=5, что означает деление каждого признака на 5 бинов. То есть, число фичей будет 5
Таким образом, будет создано 4 новых признака:
- kbins_kitchen_area
- kbins_living_area
- kbins_total_area
- kbins_house_age
- kbins_ceiling_height


SplineTransformer создает сплайн-признаки для каждого числового признака. В вашем случае используется параметр n_knots=3, что означает создание 3 узлов (knots). По умолчанию, это приводит к созданию ( n_knots + degree - 1) новых признаков для каждого исходного признака (где degree по умолчанию равен 3). Значит у нас создастся 6 новых фичей для каждого признака).

**Получается такой pipeline для предобработки:**

```
poly_transformer = PolynomialFeatures(degree=POLY_DEGREE, include_bias=False)
kbins_transformer = KBinsDiscretizer(n_bins=KBINS_N_BINS, encode='ordinal', strategy='uniform')
spline_transformer = SplineTransformer(n_knots=SPLINE_K_NOTS, degree=SPLINE_DEGREE)


catboost_category_encoder = CatBoostEncoder(return_df=False)
ohe_encoder = OneHotEncoder(drop='if_binary')


afc = AutoFeatRegressor(feateng_cols=feature_for_autofeat,
                        feateng_steps=AFC_FEATENG_STEPS,
                        max_gb=AFC_MAX_GB,
                        transformations=AFC_TRANSFORMATION,
                        n_jobs=AFC_N_JOBS)



poly_scaler_pipeline = Pipeline(steps=[
    ('poly_spline_auto', poly_transformer),
    ('scaler', StandardScaler())
])


spline_scaler_pipeline = Pipeline(steps=[
    ('spline_spline_auto', spline_transformer),
    ('scaler', StandardScaler())
])


autofeat_scaler_pipeline = Pipeline(steps=[
    ('autofeat_spline_auto', AutoFeatWrapper(feateng_cols=feature_for_autofeat)),
    ('scaler', StandardScaler())
])


tail_scaler_pipeline = Pipeline(steps=[
    ('tail_feature_scaler', StandardScaler())
])

preprocessor = ColumnTransformer(transformers=[
    ('poly', poly_scaler_pipeline, feature_for_poly_spline_transformer),
    ('spline', spline_scaler_pipeline, feature_for_poly_spline_transformer),
    ('afc', autofeat_scaler_pipeline, feature_for_autofeat),
    ('tail_scaler', tail_scaler_pipeline, feature_tail_scaler),
    ('category_encoder', catboost_category_encoder, feature_for_target_encoding),
    ('ohe', ohe_encoder, feature_for_OHE),
    ('kbins', kbins_transformer, feature_for_kbins_transformer)
],  remainder='passthrough',
    verbose_feature_names_out=True )


```


# Переопределили класс
Поскольку у autofeat не определен метод get_features_names_out, то напишем обертку на него, чтобы потом этот метод можно было вызывать в pipeline!
```
class AutoFeatWrapper(BaseEstimator, TransformerMixin):
    def __init__(self, feateng_cols, feateng_steps=AFC_FEATENG_STEPS, max_gb=AFC_MAX_GB, transformations=AFC_TRANSFORMATION, n_jobs=AFC_N_JOBS):
        self.feateng_cols = feateng_cols
        self.feateng_steps = feateng_steps
        self.max_gb = max_gb
        self.transformations = transformations
        self.n_jobs = n_jobs
        self.afc = AutoFeatRegressor(feateng_cols=self.feateng_cols,
                                     feateng_steps=self.feateng_steps,
                                     max_gb=self.max_gb,
                                     transformations=self.transformations,
                                     n_jobs=self.n_jobs)
        
    def fit(self, X, y=None):
        self.afc.fit(X, y)
        return self
    
    def transform(self, X):
        return self.afc.transform(X)
    
    def get_feature_names_out(self, input_features=None):
        # Преобразуем данные и возвращаем имена фичей из DataFrame
        transformed_X = self.afc.transform(pd.DataFrame(np.zeros((1, len(self.feateng_cols))), columns=self.feateng_cols))
        return transformed_X.columns.tolist()

```



В ручной генерации признаков используем geopy для признака километража до центра по координатам.

```
center_coords = (59.932464, 30.349258)

def calculate_distance(row: pd.Series) -> float:
    """Расчет километража от объекта до центра Питера"""
    point_coords = (row['latitude'], row['longitude'])
    return geodesic(point_coords, center_coords).kilometers


```
**Feature Selection (mlxtend) и обучение новой модели, логирование артефактов:**

Создание новых признаков — это лишь часть работы. Следующий важный шаг — это убедиться в том, что каждый из этих признаков действительно вносит положительный вклад в качество модели. Некоторые признаки могут оказывать отрицательное влияние на модель, поэтому их следует исключить из анализа.

С помощью autofeat провели отбор признаков по алгоритмам из библиотеки mlxtend:

```
sbs = SequentialFeatureSelector(model,
                                k_features=FS_SBS_K_FEATURES,
                                forward=False,
                                floating=False,
                                scoring='r2',
                                cv=2,
                                n_jobs=-1)

```

Обучил алгоритмы Sequential Backward Selection и Sequential Forward Selection. На объединении их признаков построил новое признаковое пространство. Обучил модель и залогировал. Метрика выросла.

**Подбор гиперпараметров Optuna + логирование подбора и моделей. 
Затем провел гиперпараметров на Optuna. Оно еще улучшила качество, подобрав лучшие гиперпараметры:**
```
def objective(trial: optuna.Trial) -> float:
    params = {'max_depth': trial.suggest_int('max_depth', 5, 15),
            'min_samples_leaf': trial.suggest_int('min_samples_leaf', 1, 3),
            'min_samples_split': trial.suggest_int('min_samples_split', 2, 3),
            'criterion': trial.suggest_categorical('criterion', ['absolute_error', 'friedman_mse', 'squared_error', 'poisson']),
            }

    model = DecisionTreeRegressor(**params, random_state=42)

    kf = KFold(n_splits=3, shuffle=True, random_state=42)

    r2_metrics = []

    for i, (train_index, val_index) in enumerate(kf.split(X_train, y_train)):
        train_x = X_train.iloc[train_index]
        train_y = y_train.iloc[train_index]
        val_x = X_train.iloc[val_index]
        val_y = y_train.iloc[val_index]

        model.fit(train_x, train_y)
        r2_metrics.append(r2_score(val_y, model.predict(val_x)))

    average_r2_skf = np.mean(r2_metrics)

    return average_r2_skf


with mlflow.start_run(run_name='optuna', experiment_id=experiment_id) as run:
    run_id = run.info.run_id

mlflclb = MLflowCallback(
    f"http://{TRACKING_SERVER_HOST}:{TRACKING_SERVER_PORT}",
    metric_name="r2",
    create_experiment=False,
    mlflow_kwargs = {
        "experiment_id": experiment_id, 
        "tags": {'mlflow.parentRunId': run_id}
    }
)
     
study = optuna.create_study(direction='maximize',
                           study_name=STUDY_NAME,
                           storage=STUDY_DB_NAME,
                           load_if_exists=False,
                           sampler=optuna.samplers.TPESampler())

study.optimize(objective, n_trials=10, callbacks=[mlflclb])
```
14. **Результаты экспериментов:**


**Таким образом, по таблице и графику в конце тетради мы видим, что каждый последующий этап действительно улучшает качество модели. Улучшили метрику baseline с 0.5 до 0.62! В разработки моделей и жизненого цикла это очень важные этапы. Для улучшения результатов стоит провести анализ ошибок моделей:**

1. **Рассмотреть остатки модели на:**
* Нормальность (t-test для одной выборки)
* Тест на смещение остатков (Шапиро-Уилка)
* Проверка на гомоскедастичность (Barlets test / Levens test)

2. **Проверить справедливость остатков** (Residual Fairness) - размазанность ошибки по всем наблюдениям. Это можно сделать с помощью Gini Index - оценит степень отклонения остатков от абсолютного равенства.

3. **Провести Best/Worse анализ** - рассмотреть наблюдения, при которых остатки огромные и маленькие. Это поможет выделить паттерны ошибок

4. **Запросить больше данных с сайта Недвижимости**
