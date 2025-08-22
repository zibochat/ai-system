from recommender import load_profile, recommend

if __name__ == "__main__":
    profile = load_profile(0)

    message = " سه تا سفید کننده منایب پوست من پیشنهاد بده "

    answer, log  = recommend(profile, message)
    print("\n--- پاسخ چت‌بات ---\n")
    print(answer) 
    print(log)
