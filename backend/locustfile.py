from locust import HttpUser, between, task


class CareFinderUser(HttpUser):
    wait_time = between(1, 3)
    @task
    def service_search(self):
        self.client.post("/api/search", json={
            "service":"physiotherapy", "postcode":"CO1 1AA", "radius_miles":10, "limit":10
        })
