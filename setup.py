from setuptools import setup, find_packages

setup(
    name='appy',
    version='0.1.0',
    description='Python service to speed-up API creation and db analysis',
    author='Il Tuo Nome',
    author_email='enrico@mautone.com',
    packages=find_packages(),
    install_requires=[
        'sqlalchemy',
        'pyodbc',
        'fastapi',
        'uvicorn',
        'python-jose',
        'networkx',
        'matplotlib',
        'psycopg2-binary'
    ],
    entry_points={
        'console_scripts': [
            'appy=appy.appy_service:run_server',
        ],
    },
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.6',
)
