import json, math, random, statistics, sys
configuration = json.load(open(sys.argv[1]))
design = json.load(open(sys.argv[2]))
rng = random.Random(configuration["seed"])
def fit(xs, ys, ws):
    total = sum(ws); xm = sum(w*x for w,x in zip(ws,xs))/total; ym = sum(w*y for w,y in zip(ws,ys))/total
    slope = sum(w*(x-xm)*(y-ym) for w,x,y in zip(ws,xs,ys))/sum(w*(x-xm)**2 for w,x in zip(ws,xs))
    return ym-slope*xm, slope
ratios = []
for repeat in range(configuration["repetitions"]):
    xs = design["training_x"]; sigmas = [0.1 + 1.5*x for x in xs]
    ys = [1.0 + 2.0*x + rng.gauss(0,sigma) for x,sigma in zip(xs,sigmas)]
    ols = fit(xs,ys,[1.0]*len(xs)); wls = fit(xs,ys,[1.0/(s*s) for s in sigmas])
    def error(coef):
        return math.sqrt(statistics.mean([(coef[0]+coef[1]*x-(1+2*x))**2 for x in design["holdout_x"]]))
    ratios.append(error(wls)/error(ols))
bootstrap = random.Random(configuration["seed"]+1)
medians = sorted(statistics.median(bootstrap.choices(ratios,k=len(ratios))) for _ in range(500))
summary = {"seed": configuration["seed"], "repetitions": len(ratios), "median_rmse_ratio": statistics.median(ratios), "bootstrap_median_interval_95": [medians[12],medians[487]], "criterion": "median ratio < 0.90", "supported": statistics.median(ratios)<0.90, "ratios": ratios, "limits": ["Synthetic known linear model", "Oracle variance weights", "Holdout evaluates noiseless mean response", "Bootstrap interval conditional on this design", "Known WLS reproduction; no novelty or wetlab claim"]}
print(json.dumps(summary,sort_keys=True))
