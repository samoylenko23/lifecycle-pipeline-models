import os
import pendulum
from airflow.decorators import dag, task
from plugins.messages import send_telegram_success_message, send_telegram_failure_message
from dotenv import load_dotenv

load_dotenv()

NAME_SOURCE = os.getenv('SOURCE')


@dag(
    schedule='@once',
    start_date=pendulum.datetime(2024, 1, 1, tz="UTC"),
    catchup=False,
    on_success_callback=send_telegram_success_message,
    on_failure_callback=send_telegram_failure_message,
    tags=['build_ETL_project2']
)
def prepare_building_datasets():
    import pandas as pd
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
        build_price = Table(
                'build_price',
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
                Column('studio', String),
                Column('total_area', Float),
                Column('price', Numeric),
                Column('build_year', Integer),
                UniqueConstraint('id_build_flat', name='id_build_flat')
            )

        if inspect(conn).has_table(build_price.name):
            build_price.drop(bind=conn)
        metadata.create_all(conn)


    
    @task()
    def extract() -> pd.DataFrame:
        hook = PostgresHook(NAME_SOURCE)
        conn = hook.get_conn()
        sql_query = ''' SELECT b.id AS id_build,
                            f.building_id,
                            f.id AS id_flat,
                            b.build_year,
                            b.building_type_int,
                            b.latitude,
                            b.longitude,
                            b.ceiling_height,
                            b.flats_count,
                            b.floors_total,
                            b.has_elevator,
                            f.floor,
                            f.kitchen_area,
                            f.living_area,
                            f.rooms,
                            f.is_apartment,
                            f.studio,
                            f.total_area,
                            f.price
                        FROM buildings AS b
                        LEFT JOIN flats AS f ON b.id = f.building_id'''

        data = pd.read_sql(sql_query, conn)
        conn.close()
        return data
    
    
    @task()
    def transform(data: pd.DataFrame) -> pd.DataFrame:
        # Создаем новый уникальный id
        data['id_build'] = data['id_build'].astype(str) + '_' + data['id_flat'].astype(str)
        data = data.rename(columns={'id_build': 'id_build_flat'})
        data = data.drop(['building_id', 'id_flat'], axis=1)
        
        return data
    

    @task()
    def load(data: pd.DataFrame):
        hook = PostgresHook(NAME_SOURCE)
        hook.insert_rows(
            table="build_price",
            replace=True,
            target_fields=data.columns.tolist(),
            replace_index=['id_build_flat'],
            rows=data.values.tolist()
    )

    create_table()
    data = extract()
    transformed_data = transform(data)
    load(transformed_data)

prepare_building_datasets()