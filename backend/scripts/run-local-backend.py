"""Run this project's backend on an explicit loopback port and private env file."""
import argparse
import os
from pathlib import Path
import sys

BACKEND=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file',required=True,type=Path)
    parser.add_argument('--port',type=int,default=18080)
    args=parser.parse_args()
    if args.env_file.is_symlink() or not args.env_file.is_file() or not 1024<=args.port<=65535:
        parser.exit(2,'A private environment file and valid local port are required\n')
    import dotenv
    from dotenv import dotenv_values
    from sqlalchemy.engine import make_url
    # Explicit file only; neither cwd dotenv discovery nor environment interpolation.
    values=dotenv_values(args.env_file.resolve(),interpolate=False)
    try:
        if not all(values.get(key) for key in ('DATABASE_URL','JWT_SECRET_KEY','RAG_ENABLED','RAG_ALLOW_MODEL_DOWNLOAD')):
            raise ValueError('Required deployment setting is missing')
        url=make_url(values['DATABASE_URL'])
        selected=Path(url.database)
        expected=args.env_file.resolve().parent/'health.db'
        if (url.drivername!='sqlite' or url.query or not selected.is_absolute()
                or selected.is_symlink() or selected.resolve()!=expected or not selected.is_file()):
            raise ValueError('Only this deployment directory SQLite file may be used')
        if values['RAG_ENABLED']!='false' or values['RAG_ALLOW_MODEL_DOWNLOAD']!='false':
            raise ValueError('Local login deployment keeps optional model downloads disabled')
    except Exception:
        parser.exit(2,'Local deployment configuration is incomplete or selects a different database; startup refused\n')
    system_keys={'PATH','SYSTEMROOT','WINDIR','TEMP','TMP','USERPROFILE','HOMEDRIVE','HOMEPATH','LOCALAPPDATA','APPDATA','PROGRAMDATA','COMSPEC','PATHEXT','NUMBER_OF_PROCESSORS','PROCESSOR_ARCHITECTURE','LANG','LC_ALL','TZ'}
    system_environment={key:value for key,value in os.environ.items() if key.upper() in system_keys}
    os.environ.clear()
    os.environ.update(system_environment)
    for key,value in values.items():
        if value is not None:
            os.environ[key]=value
    os.environ['PYTHON_DOTENV_DISABLED']='1'
    dotenv.load_dotenv=lambda *args,**kwargs:False
    os.chdir(BACKEND)
    sys.path.insert(0,str(BACKEND))
    import uvicorn
    uvicorn.run('app.main:app',host='127.0.0.1',port=args.port,access_log=False,log_level='warning')


if __name__=='__main__':
    main()
