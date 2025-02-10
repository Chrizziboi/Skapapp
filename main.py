import uvicorn

from fastapi import FastAPI

api = FastAPI()

if __name__ == "__main__":
    uvicorn.run(
        "main:api",
        host="localhost",
        port=8080,
        reload=True
    )

@api.get("/")
def read_root():
    return {"message": "Hello from Raspberry Pi and FastAPI!"}

@api.get("/lockers/{locker_id}")
def read_locker(locker_id: int):
    return {"Skap_id": locker_id, "status": "låst"}

