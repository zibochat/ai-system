from recommender import load_profile, recommend

if __name__ == "__main__":
    profile = load_profile(0)

    message = "می‌خوام یه روتین آبرسان ضدحساسیت داشته باشم"

    answer = recommend(profile, message)
    print("\n--- پاسخ چت‌بات ---\n")
    print(answer)
