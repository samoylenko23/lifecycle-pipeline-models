import os
import pendulum
from dotenv import load_dotenv
from airflow.decorators import dag, task
from plugins.messages import send_telegram_success_message, send_telegram_failure_message

load_dotenv()

NAME_SOURCE = os.getenv('SOURCE')


@dag(
    schedule='@once',
    start_date=pendulum.datetime(2024, 1, 1, tz="UTC"),
    catchup=False,
    on_success_callback=send_telegram_success_message,
    on_failure_callback=send_telegram_failure_message,
    tags=['clean_build_ETL_project2']
)
def clean_building_datasets():
    import pandas as pd
    import numpy as np
    from airflow.providers.postgres.hooks.postgres import PostgresHook
    from sqlalchemy import (Table, MetaData, Column,
                            Integer, Float, String,
                            UniqueConstraint, Numeric)
    from sqlalchemy import inspect

    @task()
    def create_table():
        hook = PostgresHook(NAME_SOURCE)
        conn = hook.get_sqlalchemy_engine()
        metadata = MetaData()
        clean_build_price = Table(
                'clean_dataset_build_price_2',
                metadata,
                Column('id', Integer, primary_key=True, autoincrement=True),
                Column('id_build_flat', String),
                Column('building_type_int', Integer),
                Column('latitude', Float),
                Column('longitude', Float),
                Column('ceiling_height', Float),
                Column('flats_count', Integer),
                Column('floors_total', Integer),
                Column('has_elevator', String),
                Column('floor', Integer),
                Column('kitchen_area', Float),
                Column('living_area', Float),
                Column('rooms', Integer),
                Column('is_apartment', String),
                Column('total_area', Float),
                Column('price', Numeric),
                Column('build_year', Integer),
                UniqueConstraint('id_build_flat', name='id_build_flat_in_table_clean_dataset2')
            )

        if inspect(conn).has_table(clean_build_price.name):
            # Дропаем таблицу, чтобы записать новые данные
            clean_build_price.drop(bind=conn)
        metadata.create_all(conn)


    
    @task()
    def extract() -> pd.DataFrame:
        hook = PostgresHook(NAME_SOURCE)
        conn = hook.get_conn()

        sql_query = ''' SELECT * FROM build_price'''

        data = pd.read_sql(sql_query, conn)
        conn.close()
        return data
    
    
    @task()
    def transform(data: pd.DataFrame) -> pd.DataFrame:

        def drop_dupl(data: pd.DataFrame) -> pd.DataFrame:
            '''Удаление явных дубликатов. Удаляем строки,
                в которых все значения совпадают кроме id и id_build_flat'''
            data = data.drop_duplicates(subset=data.drop(['id', 'id_build_flat'], axis=1).columns)
            return data
        
        def remove_outliers(data: pd.DataFrame) -> pd.DataFrame:
            num_cols = data.select_dtypes(['float', 'int']).columns
            threshold = 1.7
            potential_outliers = pd.DataFrame() 

            for col in num_cols:
                Q1 = np.percentile(data[col], [25])[0]
                Q3 = np.percentile(data[col], [75])[0]
                IQR = Q3 - Q1
                margin = threshold * IQR
                lower = Q1 - margin
                upper = Q3 + margin
                potential_outliers[col] = ~data[col].between(lower, upper)

            outliers = potential_outliers.any(axis=1)
            return data[~outliers]


        def fill_missing_values(data: pd.DataFrame) -> pd.DataFrame:
            '''Заполняем пропуски'''
            cols_with_nans = data.isnull().sum()
            cols_with_nans = cols_with_nans[cols_with_nans > 0].index
            for col in cols_with_nans:
                if data[col].dtype in [float]:
                    fill_value = data[col].mean()
                elif data[col].dtype in [int]:
                    fill_value = int(data[col].mean())
                elif data[col].dtype == 'object':
                    fill_value = data[col].mode().iloc[0]
                data[col] = data[col].fillna(fill_value)
            return data         
        
        # Удаляем неинформативный столбец, там все значения одинаковые
        data = data.drop(['studio'], axis=1)
        
        data = drop_dupl(data)
        data = remove_outliers(data)
        data = fill_missing_values(data)

        # Переведу ее в категориальные, чтобы не скэйлить потом по ошибке
        data['building_type_int'] = data['building_type_int'].astype(str)

        return data
    

    @task()
    def load(data: pd.DataFrame):
        hook = PostgresHook(NAME_SOURCE)
        hook.insert_rows(
            table="clean_dataset_build_price_2",
            replace=True,
            target_fields=data.columns.tolist(),
            replace_index=['id_build_flat'],
            rows=data.values.tolist()
    )

    create_table()
    data = extract()
    transformed_data = transform(data)
    load(transformed_data)

clean_building_datasets()