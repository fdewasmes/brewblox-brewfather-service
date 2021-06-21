from brewblox_service import http


class SparkServiceClient:
    # TODO properly handle host and service
    SPARK_HOST = '192.168.178.192'
    SPARK_SERVICE = 'spark-one'
    SPARK_BLOCKS_API_PATH = 'blocks'
    SPARK_API_BASE_URL = f'http://{SPARK_HOST}/{SPARK_SERVICE}/{SPARK_BLOCKS_API_PATH}'

    def __init__(self, app):
        self.app = app

    async def read_blocks(self) -> list:
        session = http.session(self.app)
        response = await session.post(f'{self.SPARK_API_BASE_URL}/all/read')
        block_list = await response.json()
        return block_list

    async def read_block(self, obj: dict) -> dict:
        session = http.session(self.app)
        response = await session.post(f'{self.SPARK_API_BASE_URL}/read', data=obj)
        block = await response.json()
        return block

    async def patch_block(self, obj: dict) -> dict:
        session = http.session(self.app)
        response = await session.post(
            f'{self.SPARK_API_BASE_URL}/patch',
            json=obj)
        block = await response.json()
        return block
