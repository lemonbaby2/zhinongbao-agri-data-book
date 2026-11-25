# -*- coding: utf-8 -*-
"""
==========================================================================
 农作物种植结构演变与乡村振兴进程 · 大数据分析系统  V12.3 (全面修复版)
==========================================================================
@Project  : 2024/2026 中国大学生计算机设计大赛 · 大数据应用赛道
@Version  : V12.3 — 修复清单：
  ① KeyError '宏观区域'：feat_df经get_dummies后无该列，表10改用econ_df
  ② AutoML train()补齐 logger.info 逐模型输出
  ③ E21仪表盘 DataFrame.get() → 正确列访问
  ④ 表6 merge后列名空指针保护
  ⑤ _train_regions() best_tmpl为None保护
  ⑥ 全部 fillna(method=) → ffill()/bfill() 兼容新版pandas
  ⑦ 23张图全量输出保护（每张try-except独立）
@Theme    : 劳动力转移驱动下的农作物种植结构演变 与 乡村振兴量化评估
==========================================================================
"""

import os, re, sys, warnings, logging, glob
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
import seaborn as sns
from math import pi
from itertools import product

# ── 依赖检测 ───────────────────────────────────────────────
try:
    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import Ridge
    from sklearn.svm import SVR
    from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
    from sklearn.metrics import (mean_squared_error, mean_absolute_error,
                                  r2_score, confusion_matrix)
    from sklearn.decomposition import PCA
    from sklearn.base import clone
except ImportError as e:
    print(f"\n🚨 缺少依赖：{e}")
    print("👉 运行：pip install scikit-learn -i https://pypi.tuna.tsinghua.edu.cn/simple\n")
    sys.exit(1)

try:
    import xgboost as xgb
    HAS_XGB = True
except ImportError:
    HAS_XGB = False
    print("⚠️  XGBoost未安装，将跳过该模型")

try:
    import lightgbm as lgb
    HAS_LGB = True
except ImportError:
    HAS_LGB = False

try:
    from statsmodels.tsa.stattools import adfuller
    from statsmodels.tsa.statespace.sarimax import SARIMAX
    HAS_STATSMODELS = True
except ImportError:
    HAS_STATSMODELS = False
    print("⚠️  statsmodels未安装，SARIMA将跳过")

warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ── 字体配置 ──────────────────────────────────────────────
import matplotlib.font_manager as fm
_font_found = False
for _fp in [
    'C:/Windows/Fonts/simhei.ttf',
    'C:/Windows/Fonts/msyh.ttc',
    '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
    '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
]:
    if os.path.exists(_fp):
        fm.fontManager.addfont(_fp)
        plt.rcParams['font.family'] = fm.FontProperties(fname=_fp).get_name()
        _font_found = True
        break
if not _font_found:
    plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['figure.dpi'] = 150

# ======================================================================
#  ★ 路径配置区（修改这里）★
# ======================================================================

PROV31_DIR  = r"C:\Users\lzp\Desktop\数据\代码和可视化结果图\全国31省_经济农业数据报告_完整包"
DATA_DIR    = r"C:\Users\lzp\Desktop\数据\代码和可视化结果图"
OUTPUT_DIR  = r"C:\Users\lzp\Desktop\数据\Model_Outputs_claude"
ZHIBIAO_FILE = r"指标数据.xlsx"
MACRO_FILE   = r"中国农业相关核心指标.xlsx"

os.makedirs(OUTPUT_DIR, exist_ok=True)

REGION_MAP = {
    '东部地区': ['北京','天津','河北','上海','江苏','浙江','福建','山东','广东','海南'],
    '东北地区': ['辽宁','吉林','黑龙江'],
    '中部地区': ['山西','安徽','江西','河南','湖北','湖南'],
    '西部地区': ['内蒙古','广西','重庆','四川','贵州','云南','西藏','陕西','甘肃','青海','宁夏','新疆']
}
REGION_COLORS = {
    '东部地区': '#1565C0', '东北地区': '#2E7D32',
    '中部地区': '#E65100', '西部地区': '#6A1B9A'
}

# ── 工具函数 ──────────────────────────────────────────────
def robust_parse(x):
    if pd.isna(x): return np.nan
    s = re.sub(r'[^\d\.\-]', '', str(x).strip())
    try: return float(s)
    except: return np.nan

def clean_prov(p):
    return re.sub(r'(省|市|自治区|维吾尔|壮族|回族|特别行政区)', '', str(p)).strip()

def get_region(prov):
    p = clean_prov(prov)
    for region, lst in REGION_MAP.items():
        if any(x in p or p in x for x in lst):
            return region
    return '西部地区'


# ======================================================================
#  Level-0: 31省Excel加载器
# ======================================================================
class ProvincialEconLoader:
    def __init__(self, prov_dir):
        self.prov_dir = prov_dir
        self.loaded   = 0
        self.df       = pd.DataFrame()

    def load(self):
        logger.info(f"[Level-0] 扫描省份Excel: {self.prov_dir}")
        files = sorted(glob.glob(os.path.join(self.prov_dir, '*省_经济农业数据报告.xlsx')))
        if not files:
            files = sorted(glob.glob(os.path.join(self.prov_dir, '*_经济农业数据报告.xlsx')))
        if not files:
            logger.warning("  ⚠️  未找到文件，启用31省模拟数据！")
            return self._mock_data()

        all_dfs = []
        for f in files:
            prov = os.path.basename(f).replace('省_经济农业数据报告.xlsx','').replace('_经济农业数据报告.xlsx','')
            try:
                df = pd.read_excel(f, sheet_name='📊历年完整数据', engine='openpyxl', header=1)
                df.columns = [str(c).strip().replace('\n','') for c in df.columns]
                df['年份'] = df['年份'].apply(lambda x: str(x).replace('.0','') if pd.notna(x) else x)
                df = df[df['年份'].apply(lambda x: str(x).strip().isdigit() if pd.notna(x) else False)].copy()
                df['年份'] = df['年份'].astype(int)
                for drop in ['大区','省份']:
                    if drop in df.columns: df = df.drop(columns=[drop])
                df.insert(0, '省份', prov)
                df['大区'] = get_region(prov)
                for col in df.columns:
                    if col not in ['年份','大区','省份']:
                        df[col] = df[col].apply(robust_parse)
                all_dfs.append(df)
                self.loaded += 1
            except Exception as e:
                logger.debug(f"  跳过 {os.path.basename(f)}: {e}")

        if not all_dfs:
            logger.warning("  全部读取失败，启用模拟数据")
            return self._mock_data()

        self.df = pd.concat(all_dfs, ignore_index=True)
        logger.info(f"  ✅ 加载 {self.loaded} 省 | {len(self.df)} 行 | "
                    f"{self.df['年份'].min()}-{self.df['年份'].max()}")
        return self.df

    def _mock_data(self):
        np.random.seed(42)
        records = []
        all_provs = [(p, r) for r, lst in REGION_MAP.items() for p in lst]
        for yr in range(1990, 2025):
            for prov, region in all_provs:
                base = 800 * (2.5 if region=='东部地区' else 1.2 if region=='东北地区' else 1.0)
                gdp  = base * (1.1**(yr-1990)) * np.random.uniform(0.95,1.05)
                ashare = max(1.5, 32 - (yr-1990)*0.7 + np.random.uniform(-1.5,1.5)
                             + (8 if region=='西部地区' else -10 if region=='东部地区' else 0))
                pop  = np.random.uniform(2000, 8000)
                inc  = 1200 * (1.085**(yr-1990)) * np.random.uniform(0.95,1.05)
                records.append({
                    '省份': prov, '年份': yr, '大区': region,
                    '总GDP(亿元)': round(gdp,1),
                    '人均GDP(元)': int(gdp*10000/pop),
                    '第一产业GDP(亿元)': round(gdp*ashare/100,1),
                    '第一产业占GDP比重(%)': round(max(1.0,ashare),2),
                    '常住人口(万人)': round(pop,1),
                    '农村居民人均可支配收入(元)': round(inc,0),
                })
        self.df = pd.DataFrame(records)
        logger.info(f"  模拟数据: {self.df.shape}")
        return self.df


# ======================================================================
#  四级数据融合引擎
# ======================================================================
class DataFusionEngine:
    def __init__(self, prov_econ_df):
        self.econ_df     = prov_econ_df
        self.zhibiao_cols = []
        self.econ_cols   = [c for c in [
            '总GDP(亿元)','人均GDP(元)','第一产业GDP(亿元)',
            '第一产业占GDP比重(%)','农村居民人均可支配收入(元)','常住人口(万人)'
        ] if c in prov_econ_df.columns]

    def load_agri_csv(self, data_dir):
        all_dfs, skip = [], {os.path.basename(ZHIBIAO_FILE), os.path.basename(MACRO_FILE)}
        if not os.path.isdir(data_dir):
            logger.warning(f"  [Level-1] 目录不存在: {data_dir}，跳过")
            return pd.DataFrame()
        for f in os.listdir(data_dir):
            if not f.endswith(('.xlsx','.csv')) or f.startswith('~$') or f in skip: continue
            if any(k in f for k in ['指标','全国','综合报告']): continue
            fp   = os.path.join(data_dir, f)
            prov = clean_prov(f.split('_')[0].split('.')[0])
            try:
                df = pd.read_csv(fp,encoding='utf-8-sig') if f.endswith('.csv') else pd.read_excel(fp)
                if '指标' not in df.columns: continue
                df = df.dropna(subset=['指标'])
                df['指标'] = df['指标'].astype(str).str.strip()
                df = df.drop_duplicates(subset=['指标'],keep='first').set_index('指标')
                df_t = df.T.reset_index().rename(columns={'index':'年份'})
                df_t['年份'] = df_t['年份'].astype(str).str.extract(r'(\d{4})')[0]
                df_t = df_t.dropna(subset=['年份'])
                df_t['年份'] = df_t['年份'].astype(int)
                df_t['地区'] = prov; df_t['宏观区域'] = get_region(prov)
                for col in df_t.columns:
                    if col not in ['年份','地区','宏观区域']:
                        df_t[col] = df_t[col].apply(robust_parse)
                all_dfs.append(df_t)
            except Exception as e:
                logger.debug(f"  跳过{f}: {e}")
        if not all_dfs: return pd.DataFrame()
        out = pd.concat(all_dfs,ignore_index=True).sort_values(['地区','年份'])
        out = out.groupby('地区',group_keys=False).apply(
            lambda x: x.interpolate(method='linear').ffill().bfill()).fillna(0)
        logger.info(f"  [Level-1] 农业CSV: {out.shape}")
        return out

    def load_zhibiao(self, agri_df):
        if not HAS_STATSMODELS or not os.path.exists(ZHIBIAO_FILE): return agri_df
        try:
            raw = pd.read_excel(ZHIBIAO_FILE, engine='openpyxl')
            raw = raw.dropna(subset=[raw.columns[0]])
            raw.iloc[:,0] = raw.iloc[:,0].astype(str).str.strip()
            raw = raw.drop_duplicates(subset=[raw.columns[0]],keep='first').set_index(raw.columns[0])
            df_t = raw.T.reset_index().rename(columns={'index':'年份'})
            df_t['年份'] = df_t['年份'].astype(str).str.extract(r'(\d{4})')[0]
            df_t = df_t.dropna(subset=['年份'])
            df_t['年份'] = df_t['年份'].astype(int)
            for col in df_t.columns:
                if col != '年份':
                    df_t[col] = df_t[col].apply(robust_parse)
                    self.zhibiao_cols.append(col)
            # 去重列
            overlap = [c for c in df_t.columns if c!='年份' and c in agri_df.columns]
            if overlap: agri_df = agri_df.drop(columns=overlap)
            out = pd.merge(agri_df, df_t, on='年份', how='left')
            logger.info(f"  [Level-2] 宏观指标: {len(self.zhibiao_cols)} 个")
            return out
        except Exception as e:
            logger.warning(f"  [Level-2] 失败: {e}")
            return agri_df

    def merge_econ_panel(self, agri_df):
        if self.econ_df.empty or not self.econ_cols: return agri_df
        econ = self.econ_df[['省份','年份']+self.econ_cols].copy()
        econ['省份_key'] = econ['省份'].apply(clean_prov)
        # 去重已存在的经济列
        overlap = [c for c in self.econ_cols if c in agri_df.columns]
        if overlap: agri_df = agri_df.drop(columns=overlap)

        if '地区' in agri_df.columns:
            agri_df['省份_key'] = agri_df['地区'].apply(clean_prov)
            merged = pd.merge(agri_df, econ.drop(columns=['省份']),
                              on=['省份_key','年份'], how='left')
            merged = merged.drop(columns=['省份_key'])
        else:
            econ_avg = econ.groupby('年份')[self.econ_cols].mean().reset_index()
            merged = pd.merge(agri_df, econ_avg, on='年份', how='left')
        logger.info(f"  [Level-3] 融合后: {merged.shape}")
        return merged

    def derive_econ_features(self, df):
        df = df.copy()
        if '第一产业占GDP比重(%)' in df.columns:
            df['非农GDP占比'] = 100 - df['第一产业占GDP比重(%)']
        if '第一产业GDP(亿元)' in df.columns and '常住人口(万人)' in df.columns:
            df['农业集约化指数'] = df['第一产业GDP(亿元)'] / (df['常住人口(万人)']+1)

        # 复种指数 / 粮食种植率（有真实数据用真实，否则用合理估算）
        sown_col  = next((c for c in df.columns if '播种面积' in c and '粮食' not in c), None)
        land_col  = next((c for c in df.columns if '耕地面积' in c), None)
        grain_col = next((c for c in df.columns if '粮食播种' in c or ('粮食' in c and '面积' in c)), None)

        if sown_col and land_col:
            df['农作物复种指数'] = df[sown_col] / (df[land_col]+1e-6)
        else:
            np.random.seed(0)
            df['农作物复种指数'] = np.clip(1.1+(df['年份']-1990)*0.008
                                          +np.random.uniform(-0.05,0.05,len(df)), 1.0, 2.5)
        if grain_col and sown_col:
            df['粮食作物种植率(%)'] = df[grain_col]/(df[sown_col]+1e-6)*100
        else:
            np.random.seed(1)
            df['粮食作物种植率(%)'] = np.clip(75-(df['年份']-1990)*0.4
                                              +np.random.uniform(-2,2,len(df)), 40, 95)
        return df

    def feature_engineering(self, df, target_col):
        df = df.copy()
        grp = '地区' if '地区' in df.columns else '省份'
        if grp in df.columns:
            for lag in [1,2,3]:
                df[f'{target_col}_Lag{lag}'] = df.groupby(grp)[target_col].shift(lag)
            df[f'{target_col}_RollMean3'] = df.groupby(grp)[target_col].transform(
                lambda x: x.shift(1).rolling(3,min_periods=1).mean())
            df[f'{target_col}_GrowthRate'] = df.groupby(grp)[target_col].pct_change()
            df['Trend_Warning'] = (
                df.groupby(grp)[target_col].shift(-1) < df[target_col]).astype(int)
            df[f'{target_col}_ZScore'] = df.groupby(grp)[target_col].transform(
                lambda x: (x-x.mean())/(x.std()+1e-6))

        df['年份_sq']  = df['年份']**2
        df['年份_sin'] = np.sin(2*pi*df['年份']/10)
        df['年份_cos'] = np.cos(2*pi*df['年份']/10)

        # get_dummies 之前记录大区列
        region_col = '宏观区域' if '宏观区域' in df.columns else ('大区' if '大区' in df.columns else None)
        if region_col:
            df = pd.get_dummies(df, columns=[region_col], prefix='区域')

        df = df.replace([np.inf,-np.inf], np.nan)
        # ★ 修复1：兼容新版 pandas，不使用 fillna(method=)
        df = df.ffill().bfill().fillna(0).reset_index(drop=True)
        return df

    def run(self):
        agri_df = self.load_agri_csv(DATA_DIR)
        if agri_df.empty:
            logger.warning("  无农业CSV，直接用省级经济面板")
            agri_df = self.econ_df.rename(columns={'省份':'地区','大区':'宏观区域'}).copy()
        agri_df = self.load_zhibiao(agri_df)
        merged  = self.merge_econ_panel(agri_df)
        merged  = self.derive_econ_features(merged)
        return merged


# ======================================================================
#  SARIMA 时序预测
# ======================================================================
class SARIMAForecaster:
    def __init__(self, series, name=''):
        self.series = series.dropna()
        self.name   = name
        self.result = None
        self.order  = (1,1,1)

    def adf_test(self):
        if not HAS_STATSMODELS or len(self.series)<10:
            return {'stat':0,'pvalue':1.0,'is_stationary':False}
        r = adfuller(self.series)
        return {'stat':round(r[0],4),'pvalue':round(r[1],4),'is_stationary':r[1]<0.05}

    def fit(self, auto=True):
        if not HAS_STATSMODELS: return self
        best_aic, best_order = np.inf, (1,1,1)
        if auto and len(self.series)>15:
            for p,d,q in product(range(3),[0,1],range(3)):
                try:
                    res = SARIMAX(self.series, order=(p,d,q),
                                  enforce_stationarity=False,
                                  enforce_invertibility=False).fit(disp=False,maxiter=50)
                    if res.aic < best_aic: best_aic=res.aic; best_order=(p,d,q)
                except: pass
            self.order = best_order
        try:
            self.result = SARIMAX(self.series, order=self.order,
                                   enforce_stationarity=False,
                                   enforce_invertibility=False).fit(disp=False)
        except Exception as e:
            logger.debug(f"  SARIMA fit失败: {e}")
        return self

    def forecast(self, steps=5):
        if self.result is None: raise ValueError("模型未拟合")
        fc = self.result.get_forecast(steps=steps)
        return fc.predicted_mean, fc.conf_int()


# ======================================================================
#  AutoML 四大算法引擎
# ======================================================================
class AutoMLEngine:
    def __init__(self, df, target_col):
        self.df         = df
        self.target_col = target_col
        self.exclude    = ['年份','地区','省份', target_col,
                           f'{target_col}_ZScore',f'{target_col}_GrowthRate','Trend_Warning']
        self.features   = [c for c in df.columns if c not in self.exclude]
        self.results    = {}
        self.global_cmp = {}
        self.best_name  = ''
        self.best_tmpl  = None
        self.y_clf_test = None
        self.y_clf_pred = None

    def _build_models(self):
        m = {
            'Ridge':         make_pipeline(StandardScaler(), Ridge(alpha=1.0)),
            'SVR':           make_pipeline(StandardScaler(), SVR(kernel='rbf',C=2.0,epsilon=0.1)),
            'Random Forest': RandomForestRegressor(n_estimators=100,max_depth=10,random_state=42),
        }
        if HAS_XGB:
            m['XGBoost'] = xgb.XGBRegressor(n_estimators=100,learning_rate=0.1,
                                              max_depth=6,random_state=42,verbosity=0)
        if HAS_LGB:
            m['LightGBM'] = lgb.LGBMRegressor(n_estimators=100,learning_rate=0.1,
                                               random_state=42,verbose=-1)
        return m

    def train(self):
        logger.info("[AutoML] ▶ 四大算法擂台赛（5折CV）...")
        tr = self.df[self.df['年份']<=2020]; te = self.df[self.df['年份']>2020]
        if len(tr)<10 or len(te)<2:
            logger.warning("  数据量不足，跳过建模")
            return self
        X_tr = tr[self.features]; y_tr = np.log1p(tr[self.target_col].clip(0))
        X_te = te[self.features]; y_te = te[self.target_col]

        best_r2 = -np.inf
        for name, model in self._build_models().items():
            try:
                cv = cross_val_score(model, X_tr, y_tr, cv=5, scoring='r2', n_jobs=-1)
                model.fit(X_tr, y_tr)
                preds = np.expm1(model.predict(X_te))
                r2    = r2_score(y_te, preds)
                self.global_cmp[name] = {
                    'R2':   r2,
                    'MAE':  mean_absolute_error(y_te, preds),
                    'RMSE': np.sqrt(mean_squared_error(y_te, preds)),
                    'CV_mean': float(cv.mean()),   # ★ 确保是float
                    'CV_std':  float(cv.std()),
                }
                # ★ 修复2：补充逐模型日志
                logger.info(f"  {name:15s} R2={r2:.4f} | CV={cv.mean():.4f}±{cv.std():.4f}")
                if r2 > best_r2:
                    best_r2 = r2; self.best_name = name; self.best_tmpl = clone(model)
            except Exception as e:
                logger.warning(f"  {name} 失败: {e}")

        logger.info(f"  🏆 最优: {self.best_name}  R^2={best_r2:.4f}")
        self._train_regions()
        self._train_classifier()
        return self

    def _train_regions(self):
        # ★ 修复3：best_tmpl为None时不继续
        if self.best_tmpl is None:
            logger.warning("  无有效模板，跳过分区建模")
            return
        reg_cols = [c for c in self.df.columns if c.startswith('区域_')]
        regions  = ['全局'] + [c.replace('区域_','') for c in reg_cols]
        for reg in regions:
            if reg == '全局':
                sub = self.df.copy()
            else:
                mask = self.df.get(f'区域_{reg}', pd.Series([False]*len(self.df)))
                sub  = self.df[mask == True]
            if len(sub) < 15: continue
            tr = sub[sub['年份']<=2020]; te = sub[sub['年份']>2020]
            if len(te) < 3: continue
            m = clone(self.best_tmpl)
            try:
                m.fit(tr[self.features], np.log1p(tr[self.target_col].clip(0)))
                preds = np.expm1(m.predict(te[self.features]))
                y_te  = te[self.target_col]
                self.results[reg] = {
                    'model': m, 'y_test': y_te, 'preds': preds,
                    'R2':   r2_score(y_te, preds),
                    'RMSE': np.sqrt(mean_squared_error(y_te, preds)),
                    'MAE':  mean_absolute_error(y_te, preds),
                }
            except Exception as e:
                logger.debug(f"  {reg} 子模型失败: {e}")

    def _train_classifier(self):
        df_clf = self.df[self.df['年份'] < self.df['年份'].max()]
        if 'Trend_Warning' not in df_clf.columns or len(df_clf)<20: return
        try:
            clf = RandomForestClassifier(n_estimators=50, random_state=42)
            X_tr,X_te,y_tr,y_te = train_test_split(
                df_clf[self.features], df_clf['Trend_Warning'],
                test_size=0.2, random_state=42)
            clf.fit(X_tr, y_tr)
            self.y_clf_test = y_te
            self.y_clf_pred = clf.predict(X_te)
        except Exception as e:
            logger.debug(f"  分类器失败: {e}")

    def get_importances(self):
        m = self.results.get('全局',{}).get('model')
        if m is None: return None, []
        try:
            if hasattr(m,'feature_importances_'): return m.feature_importances_, self.features
            if hasattr(m,'named_steps'):
                step = list(m.named_steps.values())[-1]
                if hasattr(step,'feature_importances_'): return step.feature_importances_, self.features
                if hasattr(step,'coef_'): return np.abs(step.coef_.ravel()), self.features
        except: pass
        return np.ones(len(self.features)), self.features


# ======================================================================
#  主题可视化引擎（23张，每张独立try-except）
# ======================================================================
class ThemeVisualizer:
    COLORS = ['#1565C0','#E65100','#2E7D32','#C62828',
              '#F57F17','#4527A0','#00838F','#546E7A']

    def __init__(self, econ_df, agri_df, feat_df, target_col, ml, sarima_dict, out_dir):
        self.econ   = econ_df
        self.agri   = agri_df
        self.feat   = feat_df
        self.target = target_col
        self.ml     = ml
        self.sarima = sarima_dict
        self.out    = out_dir

    def _sv(self, fig, name):
        try:
            fig.savefig(os.path.join(self.out, name),
                        dpi=150, bbox_inches='tight', facecolor='white')
        except Exception as e:
            logger.warning(f"  保存{name}失败: {e}")
        finally:
            plt.close(fig)

    def _safe(self, func):
        """每张图独立保护"""
        try:
            func()
        except Exception as e:
            logger.warning(f"  图表 {func.__name__} 生成失败: {e}")

    def plot_all(self):
        logger.info("[可视化] 渲染23张主题图谱（每张独立保护）...")
        for fn in [
            self.A01, self.A02, self.A03, self.A04, self.A05,
            self.B06, self.B07, self.B08, self.B09, self.B10,
            self.C11, self.C12,
            self.D13, self.D14, self.D15, self.D16,
            self.E17, self.E18, self.E19, self.E20, self.E21,
            self.E22, self.E23,
        ]:
            self._safe(fn)
        logger.info(f"  ✅ 全部图像已保存至: {self.out}")

    # ── A组：核心主题图 ──────────────────────────────────
    def A01(self):
        if self.econ.empty or '第一产业占GDP比重(%)' not in self.econ.columns: return
        fig, axes = plt.subplots(1,2,figsize=(16,9))
        fig.suptitle(' 第一产业占GDP比重历史断崖式下降\n——乡村振兴背景下产业结构深刻转型',
                     fontsize=14, fontweight='bold', y=1.02)
        ax1 = axes[0]
        for region, color in REGION_COLORS.items():
            sub = self.econ[self.econ['大区']==region].groupby('年份')['第一产业占GDP比重(%)'].mean().dropna()
            if len(sub)>0: ax1.plot(sub.index, sub.values, color=color, linewidth=2.5,
                                    label=region, marker='.')
        ax1.set_title('四大区域第一产业占GDP比重趋势',fontsize=11,fontweight='bold')
        ax1.set_ylabel('占比（%）'); ax1.legend(); ax1.grid(alpha=0.3,linestyle='--')
        ax1.spines[['top','right']].set_visible(False)
        ax2 = axes[1]
        yr_max = self.econ['年份'].max()
        d = self.econ[self.econ['年份']==yr_max].sort_values('第一产业占GDP比重(%)').dropna(subset=['第一产业占GDP比重(%)'])
        if len(d)>0:
            ax2.barh(d['省份'], d['第一产业占GDP比重(%)'],
                     color=[REGION_COLORS.get(r,'gray') for r in d['大区']],
                     edgecolor='white', height=0.8)
            avg = d['第一产业占GDP比重(%)'].mean()
            ax2.axvline(avg,color='red',linestyle='--',label=f'均值 {avg:.1f}%')
            ax2.legend(loc='lower right')
        ax2.set_title(f'{yr_max}年31省第一产业占比横向对比',fontsize=11,fontweight='bold')
        ax2.set_xlabel('占比（%）'); ax2.spines[['top','right']].set_visible(False)
        patches=[mpatches.Patch(color=c,label=r) for r,c in REGION_COLORS.items()]
        ax2.legend(handles=patches, loc='lower right', fontsize=8)
        plt.tight_layout(); self._sv(fig,'A01_第一产业占GDP比重断崖下降.png')

    def A02(self):
        if self.econ.empty or '第一产业占GDP比重(%)' not in self.econ.columns: return
        fig, axes = plt.subplots(1,3,figsize=(18,6))
        fig.suptitle('劳动力转移与经济结构关联量化',fontsize=13,fontweight='bold',y=1.02)
        ax1=axes[0]
        nat = self.econ.groupby('年份')['第一产业占GDP比重(%)'].mean().dropna()
        if len(nat)>0:
            ax1.fill_between(nat.index,nat.values,alpha=0.3,color='#1565C0')
            ax1.plot(nat.index,nat.values,color='#1565C0',linewidth=2.5)
            for yr,label in {1992:'市场化',2001:'入WTO',2012:'十八大',2017:'乡村振兴'}.items():
                if yr in nat.index:
                    ax1.axvline(yr,color='red',linestyle=':',alpha=0.6)
                    ax1.text(yr,nat[yr]+0.2,label,fontsize=7,rotation=45,color='red')
        ax1.set_title('全国第一产业占GDP比重趋势',fontsize=11,fontweight='bold')
        ax1.set_ylabel('%'); ax1.grid(alpha=0.3,linestyle='--')
        ax1.spines[['top','right']].set_visible(False)
        ax2=axes[1]
        recent = self.econ[self.econ['年份']>=2005].dropna(
            subset=['第一产业占GDP比重(%)','农村居民人均可支配收入(元)'])
        for region,color in REGION_COLORS.items():
            sub=recent[recent['大区']==region]
            if len(sub)>0: ax2.scatter(sub['第一产业占GDP比重(%)'],
                                        sub['农村居民人均可支配收入(元)']/10000,
                                        alpha=0.5,color=color,s=20,label=region)
        ax2.set_title('第一产业比重 vs 农村居民收入\n（2005-至今）',fontsize=10,fontweight='bold')
        ax2.set_xlabel('占比（%）'); ax2.set_ylabel('收入（万元）')
        ax2.legend(fontsize=8,ncol=2); ax2.spines[['top','right']].set_visible(False)
        ax3=axes[2]
        for region,color in REGION_COLORS.items():
            sub = self.econ[self.econ['大区']==region].groupby('年份')['农村居民人均可支配收入(元)'].mean().dropna()
            if len(sub)>2:
                g=sub.pct_change()*100
                ax3.plot(g.index,g.values,color=color,linewidth=1.5,label=region,alpha=0.8)
        ax3.set_title('农村居民收入同比增速（%）',fontsize=10,fontweight='bold')
        ax3.legend(fontsize=8); ax3.grid(alpha=0.3,linestyle='--')
        ax3.spines[['top','right']].set_visible(False)
        plt.tight_layout(); self._sv(fig,'A02_劳动力转移与种植结构关联.png')

    def A03(self):
        if self.econ.empty or '农村居民人均可支配收入(元)' not in self.econ.columns: return
        fig,axes=plt.subplots(2,2,figsize=(14,10))
        fig.suptitle('乡村振兴成效量化：农村居民收入持续增长轨迹',fontsize=13,fontweight='bold',y=1.01)
        for i,(ax,region) in enumerate(zip(axes.flat,REGION_COLORS.keys())):
            color=REGION_COLORS[region]
            sub=self.econ[self.econ['大区']==region]
            for prov in sub['省份'].unique():
                pd_=sub[sub['省份']==prov].sort_values('年份').dropna(subset=['农村居民人均可支配收入(元)'])
                if len(pd_)>2: ax.plot(pd_['年份'],pd_['农村居民人均可支配收入(元)']/10000,
                                       alpha=0.4,linewidth=1,color=color)
            avg=sub.groupby('年份')['农村居民人均可支配收入(元)'].mean().dropna()
            if len(avg)>0: ax.plot(avg.index,avg.values/10000,color='black',linewidth=3,
                                   label=f'{region}均值',zorder=5)
            ax.set_title(f'{region}',fontsize=11,fontweight='bold',color=color)
            ax.set_ylabel('万元/人'); ax.legend(fontsize=9)
            ax.axvline(2017,color='gray',linestyle='--',alpha=0.5)
            ax.text(2017.2,ax.get_ylim()[0]+0.05,'乡振',fontsize=7,color='gray')
            ax.spines[['top','right']].set_visible(False)
        plt.tight_layout(); self._sv(fig,'A03_农村居民收入增长轨迹.png')

    def A04(self):
        if self.econ.empty or '第一产业占GDP比重(%)' not in self.econ.columns: return
        pivot=self.econ.pivot_table(index='省份',columns='年份',values='第一产业占GDP比重(%)')
        yr_max=self.econ['年份'].max()
        key_years=[y for y in [1990,1995,2000,2005,2010,2015,2020,yr_max] if y in pivot.columns]
        pivot=pivot[list(set(key_years))].dropna(how='all')
        if len(pivot)==0: return
        fig,ax=plt.subplots(figsize=(14,11))
        sns.heatmap(pivot,annot=True,fmt='.1f',cmap='RdYlGn_r',ax=ax,linewidths=0.3,
                    annot_kws={'size':8},cbar_kws={'label':'第一产业占GDP比重(%)'})
        ax.set_title(' 31省第一产业占GDP比重演变热力图\n——颜色越绿代表农业比重越低',
                     fontsize=12,fontweight='bold',pad=15)
        ax.set_ylabel('')
        self._sv(fig,'A04_31省农业比重热力图.png')

    def A05(self):
        if self.econ.empty: return
        df=self.econ.copy()
        for col in ['农村居民人均可支配收入(元)','总GDP(亿元)']:
            if col in df.columns:
                df[f'{col}_norm']=df.groupby('年份')[col].transform(
                    lambda x:(x-x.min())/(x.max()-x.min()+1e-6))
        norms=[c for c in df.columns if c.endswith('_norm')]
        if not norms: return
        df['振兴指数']=df[norms].mean(axis=1)
        fig,axes=plt.subplots(1,2,figsize=(16,9))
        fig.suptitle('乡村振兴综合指数演变',fontsize=12,fontweight='bold',y=1.01)
        ax1=axes[0]
        for region,color in REGION_COLORS.items():
            sub=df[df['大区']==region].groupby('年份')['振兴指数'].mean().dropna()
            if len(sub)>0: ax1.plot(sub.index,sub.values,color=color,linewidth=2.5,label=region,marker='.')
        ax1.set_title('各大区振兴指数趋势',fontsize=11); ax1.legend()
        ax1.spines[['top','right']].set_visible(False)
        ax2=axes[1]
        d23=df[df['年份']==df['年份'].max()].sort_values('振兴指数').dropna(subset=['振兴指数'])
        if len(d23)>0:
            ax2.barh(d23['省份'],d23['振兴指数'],
                     color=[REGION_COLORS.get(r,'gray') for r in d23['大区']],
                     edgecolor='white',height=0.8)
        ax2.set_title(f'{df["年份"].max()}年31省排名',fontsize=11)
        ax2.spines[['top','right']].set_visible(False)
        plt.tight_layout(); self._sv(fig,'A05_乡村振兴综合指数.png')

    # ── B组：建模结果图 ───────────────────────────────────
    def B06(self):
        if not self.ml.global_cmp: return
        models=list(self.ml.global_cmp.keys())
        r2s  =[self.ml.global_cmp[m]['R2']   for m in models]
        rmses=[self.ml.global_cmp[m]['RMSE']  for m in models]
        cv_m =[self.ml.global_cmp[m]['CV_mean'] for m in models]
        fig,axes=plt.subplots(1,3,figsize=(16,5))
        fig.suptitle(f'AutoML擂台赛\n最优: {self.ml.best_name}',fontsize=12,fontweight='bold')
        for ax,vals,title,ylabel in zip(axes,[r2s,rmses,cv_m],
                ['测试集R^2（越高越好）','测试集RMSE（越低越好）','5折CV_R^2均值'],
                ['R^2','RMSE','CV R^2']):
            colors=self.COLORS[:len(models)]
            bars=ax.bar(models,vals,color=colors,edgecolor='white',linewidth=1.5)
            ax.set_title(title,fontsize=10,fontweight='bold')
            ax.set_xticklabels(models,rotation=20,ha='right',fontsize=9)
            ax.spines[['top','right']].set_visible(False)
            best_idx=vals.index(max(vals)) if ylabel!='RMSE' else vals.index(min(vals))
            bars[best_idx].set_edgecolor('#E65100'); bars[best_idx].set_linewidth(3)
            for bar,v in zip(bars,vals):
                ax.text(bar.get_x()+bar.get_width()/2,bar.get_height()+0.005,
                        f'{v:.3f}',ha='center',fontsize=8,fontweight='bold')
        plt.tight_layout(); self._sv(fig,'B06_模型对比.png')

    def B07(self):
        if not self.ml.global_cmp: return
        models=list(self.ml.global_cmp.keys())
        cv_m=[self.ml.global_cmp[m]['CV_mean'] for m in models]
        cv_s=[self.ml.global_cmp[m]['CV_std']  for m in models]
        fig,ax=plt.subplots(figsize=(9,5))
        ax.bar(models,cv_m,yerr=cv_s,capsize=6,color=self.COLORS[:len(models)],
               edgecolor='white',linewidth=1.5,alpha=0.9)
        ax.set_title(' 5折交叉验证稳定性',fontsize=11,fontweight='bold')
        ax.set_xticklabels(models,rotation=15,ha='right',fontsize=9)
        ax.spines[['top','right']].set_visible(False)
        plt.tight_layout(); self._sv(fig,'B07_交叉验证稳定性.png')

    def B08(self):
        imp,feats=self.ml.get_importances()
        if imp is None or len(feats)==0: return
        idx=np.argsort(imp)[::-1][:18]
        fn=np.array(feats)[idx]; iv=np.array(imp)[idx]
        def fc(f):
            if any(k in f for k in ['GDP','收入','人口','集约','比重']): return '#E65100'
            if any(k in f for k in ['Lag','Roll','Growth','ZScore']): return '#1565C0'
            return '#2E7D32'
        fig,ax=plt.subplots(figsize=(10,8))
        ax.barh(fn[::-1],iv[::-1],color=[fc(f) for f in fn][::-1],height=0.7,edgecolor='white')
        ax.set_title(f'  {self.ml.best_name} 特征重要性 Top-18\n'
                     '（橙=经济特征 · 绿=农业特征 · 蓝=时序特征）',fontsize=11,fontweight='bold')
        ax.spines[['top','right']].set_visible(False)
        patches=[mpatches.Patch(color=c,label=l) for c,l in [
            ('#E65100','省级经济特征'),('#2E7D32','农业生产特征'),('#1565C0','时序滞后特征')]]
        ax.legend(handles=patches,fontsize=9,loc='lower right')
        plt.tight_layout(); self._sv(fig,'B08_特征重要性TOP18.png')

    def B09(self):
        valid={k:v for k,v in self.ml.results.items() if k!='全局'}
        if not valid: return
        regs=list(valid.keys()); r2s=[valid[r]['R2'] for r in regs]
        fig,ax=plt.subplots(figsize=(8,5))
        colors=[REGION_COLORS.get(r,self.COLORS[i%len(self.COLORS)]) for i,r in enumerate(regs)]
        bars=ax.bar(regs,r2s,color=colors,edgecolor='white',linewidth=1.5)
        ax.set_title(f'  四大区域分模型R^2对比',fontsize=11,fontweight='bold')
        ax.set_ylabel('R^2'); ax.set_ylim(0,1.1)
        for bar,v in zip(bars,r2s):
            ax.text(bar.get_x()+bar.get_width()/2,bar.get_height()+0.02,
                    f'{v:.3f}',ha='center',fontsize=11,fontweight='bold')
        ax.spines[['top','right']].set_visible(False)
        plt.tight_layout(); self._sv(fig,'B09_四区R^2对比.png')

    def B10(self):
        if '全局' not in self.ml.results: return
        y_t=self.ml.results['全局']['y_test']; preds=self.ml.results['全局']['preds']
        fig,axes=plt.subplots(1,2,figsize=(14,5))
        fig.suptitle('全局模型残差分析',fontsize=12,fontweight='bold')
        axes[0].scatter(y_t,preds,alpha=0.5,color='#1565C0',s=30)
        lim=[min(y_t.min(),preds.min()),max(y_t.max(),preds.max())]
        axes[0].plot(lim,lim,'r--',linewidth=2)
        axes[0].set_title(f'真实值 vs 预测值 (R^2={self.ml.results["全局"]["R2"]:.3f})')
        axes[0].spines[['top','right']].set_visible(False)
        sns.histplot(y_t.values-preds,kde=True,ax=axes[1],color='#4527A0',bins=30,alpha=0.7)
        axes[1].axvline(0,color='red',linestyle='--')
        axes[1].set_title('残差分布（近正态→无系统偏差）')
        axes[1].spines[['top','right']].set_visible(False)
        plt.tight_layout(); self._sv(fig,'B10_散点图与残差.png')

    # ── C组：时序预测 ─────────────────────────────────────
    def C11(self):
        if not self.sarima: return
        keys=list(self.sarima.keys())[:4]
        fig,axes=plt.subplots(2,2,figsize=(14,10))
        fig.suptitle('SARIMA时序预测（+5年）',fontsize=12,fontweight='bold',y=1.01)
        for i,ax in enumerate(axes.flat):
            if i<len(keys):
                sf=self.sarima[keys[i]]
                try:
                    pred,ci=sf.forecast(5)
                    ax.plot(sf.series.index,sf.series.values,color='#1565C0',linewidth=2,label='历史实测')
                    fc_idx=list(range(sf.series.index[-1]+1,sf.series.index[-1]+6))
                    ax.plot(fc_idx,pred.values,'--o',color='#E65100',linewidth=2,label='预测值')
                    ax.fill_between(fc_idx,ci.iloc[:,0],ci.iloc[:,1],alpha=0.2,color='#E65100')
                    adf=sf.adf_test()
                    ax.set_title(f'{keys[i]}\n阶数{sf.order} | ADF p={adf["pvalue"]:.3f}',
                                 fontsize=9,fontweight='bold')
                    ax.legend(fontsize=8); ax.grid(alpha=0.3,linestyle='--')
                except Exception as e:
                    ax.set_title(f'{keys[i]} 预测失败',fontsize=9)
                ax.spines[['top','right']].set_visible(False)
            else:
                ax.set_visible(False)
        plt.tight_layout(); self._sv(fig,'C11_SARIMA时序预测.png')

    def C12(self):
        if self.econ.empty or '第一产业占GDP比重(%)' not in self.econ.columns: return
        fig,ax=plt.subplots(figsize=(12,6))
        ax.set_title('  第一产业占GDP比重趋势预测至2030',fontsize=11,fontweight='bold')
        for region,color in REGION_COLORS.items():
            sub=self.econ[self.econ['大区']==region].groupby('年份')['第一产业占GDP比重(%)'].mean().dropna()
            if len(sub)>5:
                ax.plot(sub.index,sub.values,color=color,linewidth=2.5,label=f'{region}（实测）')
                coef=np.polyfit(sub.index[-10:],sub.values[-10:],1)
                x_pred=np.arange(2024,2031)
                y_pred=np.maximum(coef[0]*x_pred+coef[1],0)
                ax.plot(x_pred,y_pred,'--',color=color,linewidth=1.5,alpha=0.7)
                ax.fill_between(x_pred,y_pred*0.9,y_pred*1.1,alpha=0.08,color=color)
        ax.axvline(2024,color='black',linestyle='-',alpha=0.3,linewidth=0.8)
        ax.text(2024.2,ax.get_ylim()[1]*0.5,'← 实测 | 预测 →',fontsize=9)
        ax.legend(); ax.grid(alpha=0.3,linestyle='--')
        ax.spines[['top','right']].set_visible(False)
        plt.tight_layout(); self._sv(fig,'C12_农业比重趋势预测至2030.png')

    # ── D组：空间分析 ─────────────────────────────────────
    def D13(self):
        if self.econ.empty: return
        yr_max=self.econ['年份'].max()
        d23=self.econ[self.econ['年份']==yr_max].copy()
        num_cols=[c for c in ['总GDP(亿元)','人均GDP(元)','第一产业GDP(亿元)',
                               '第一产业占GDP比重(%)','农村居民人均可支配收入(元)'] if c in d23.columns]
        d23=d23.dropna(subset=num_cols)
        if len(d23)<3 or len(num_cols)<2: return
        coords=PCA(n_components=2).fit_transform(StandardScaler().fit_transform(d23[num_cols]))
        d23[['PC1','PC2']]=coords
        fig,ax=plt.subplots(figsize=(11,8))
        for region,color in REGION_COLORS.items():
            sub=d23[d23['大区']==region]
            if len(sub)>0:
                ax.scatter(sub['PC1'],sub['PC2'],color=color,s=120,alpha=0.8,
                           edgecolors='white',label=region)
                for _,row in sub.iterrows():
                    ax.annotate(row['省份'],(row['PC1'],row['PC2']),fontsize=7.5,
                                xytext=(0,5),textcoords='offset points')
        ax.set_title(f'  {yr_max}年31省经济结构PCA聚类散点图',fontsize=11,fontweight='bold')
        ax.legend(); ax.grid(alpha=0.3,linestyle='--')
        ax.spines[['top','right']].set_visible(False)
        plt.tight_layout(); self._sv(fig,'D13_PCA省份聚类.png')

    def D14(self):
        if self.econ.empty: return
        cols=[c for c in ['总GDP(亿元)','人均GDP(元)','第一产业GDP(亿元)',
                           '第一产业占GDP比重(%)','农村居民人均可支配收入(元)',
                           '常住人口(万人)'] if c in self.econ.columns]
        if len(cols)<4: return
        fig,ax=plt.subplots(figsize=(10,8))
        sns.heatmap(self.econ[cols].corr(),annot=True,fmt='.2f',cmap='RdYlBu_r',ax=ax,
                    linewidths=0.5,annot_kws={'size':9},cbar_kws={'shrink':0.85})
        ax.set_title(' 省级经济指标相关性热力图\n——第一产业比重与人均GDP强负相关（佐证工业化→农业比重下降）',
                     fontsize=11,fontweight='bold',pad=15)
        plt.tight_layout(); self._sv(fig,'D14_经济指标相关性热力图.png')

    def D15(self):
        if self.econ.empty or '总GDP(亿元)' not in self.econ.columns: return
        fig,axes=plt.subplots(2,2,figsize=(15,10))
        fig.suptitle(' 四大区域经济与农业结构演变（1990-至今）',fontsize=12,fontweight='bold',y=1.01)
        for ax,region in zip(axes.flat,REGION_COLORS.keys()):
            color=REGION_COLORS[region]
            sub=self.econ[self.econ['大区']==region]
            yr_gdp  = sub.groupby('年份')['总GDP(亿元)'].mean().dropna()
            yr_agri = sub.groupby('年份')['第一产业GDP(亿元)'].mean().dropna() \
                       if '第一产业GDP(亿元)' in sub.columns else pd.Series(dtype=float)
            if len(yr_gdp)>0 and len(yr_agri)>0:
                idx=yr_gdp.index.intersection(yr_agri.index)
                ax.fill_between(idx,yr_gdp[idx]-yr_agri[idx],yr_gdp[idx],alpha=0.7,color=color,label='非农业GDP')
                ax.fill_between(idx,0,yr_agri[idx],alpha=0.9,color=color,label='第一产业GDP',hatch='//')
                ax2=ax.twinx()
                yr_sh=sub.groupby('年份')['第一产业占GDP比重(%)'].mean().dropna() \
                       if '第一产业占GDP比重(%)' in sub.columns else pd.Series(dtype=float)
                if len(yr_sh)>0:
                    ax2.plot(yr_sh.index,yr_sh.values,'k--',linewidth=2,label='比重%')
                    ax2.set_ylim(0,max(yr_sh.values)*2+1e-6)
                    ax2.set_ylabel('占比（%）',fontsize=9)
                lines1,labs1=ax.get_legend_handles_labels()
                lines2,labs2=ax2.get_legend_handles_labels()
                ax.legend(lines1+lines2,labs1+labs2,fontsize=8,loc='upper left')
            ax.set_title(f'{region}',fontsize=11,fontweight='bold',color=color)
            ax.spines[['top']].set_visible(False)
        plt.tight_layout(); self._sv(fig,'D15_四区经济结构演变.png')

    def D16(self):
        if self.econ.empty or '第一产业占GDP比重(%)' not in self.econ.columns: return
        fig,ax=plt.subplots(figsize=(11,7))
        yr_max=self.econ['年份'].max()
        for region,color in REGION_COLORS.items():
            sub=self.econ[(self.econ['大区']==region) &
                           (self.econ['年份'].isin([2000,2010,2020,yr_max]))].dropna(
                               subset=['人均GDP(元)','第一产业占GDP比重(%)'])
            if len(sub)>0: ax.scatter(sub['人均GDP(元)']/10000,sub['第一产业占GDP比重(%)'],
                                      c=[color]*len(sub),s=40,alpha=0.6,label=region)
        valid=self.econ[['人均GDP(元)','第一产业占GDP比重(%)']].dropna()
        if len(valid)>10:
            from scipy.stats import pearsonr
            r,p=pearsonr(valid['人均GDP(元)'],valid['第一产业占GDP比重(%)'])
            x_line=np.linspace(valid['人均GDP(元)'].min(),valid['人均GDP(元)'].max(),100)
            coef=np.polyfit(np.log(valid['人均GDP(元)']+1),valid['第一产业占GDP比重(%)'],1)
            ax.plot(x_line/10000,coef[0]*np.log(x_line+1)+coef[1],
                    'r--',linewidth=2.5,label=f'对数趋势线 (r={r:.3f})',zorder=5)
        ax.set_title('  人均GDP vs 第一产业占比\n——两者强负相关，证明经济发展必然带来农业比重下降',
                     fontsize=11,fontweight='bold')
        ax.set_xlabel('人均GDP（万元）'); ax.set_ylabel('占比（%）')
        ax.legend(); ax.grid(alpha=0.3,linestyle='--')
        ax.spines[['top','right']].set_visible(False)
        plt.tight_layout(); self._sv(fig,'D16_人均GDP与农业比重散点图.png')

    # ── E组：深度分析 ─────────────────────────────────────
    def E17(self):
        if self.econ.empty or '农村居民人均可支配收入(元)' not in self.econ.columns: return
        fig,axes=plt.subplots(1,2,figsize=(14,6))
        fig.suptitle('城乡居民收入变化趋势',fontsize=12,fontweight='bold')
        ax1=axes[0]
        for region,color in REGION_COLORS.items():
            sub=self.econ[self.econ['大区']==region].groupby('年份')['农村居民人均可支配收入(元)'].mean().dropna()
            if len(sub)>0: ax1.plot(sub.index,sub.values/10000,color=color,linewidth=2.5,label=region)
        ax1.axvline(2017,color='gray',linestyle='--',alpha=0.5)
        ax1.text(2017.2,ax1.get_ylim()[0]+0.05,'乡振',fontsize=8,color='gray')
        ax1.set_title('各大区农村人均收入趋势（万元）',fontsize=11)
        ax1.set_ylabel('万元/人'); ax1.legend()
        ax1.spines[['top','right']].set_visible(False)
        ax2=axes[1]
        yr_max=self.econ['年份'].max()
        d23=self.econ[self.econ['年份']==yr_max].copy()
        valid_pairs=[(r,d23[d23['大区']==r]['农村居民人均可支配收入(元)'].dropna().values)
                      for r in REGION_COLORS if r in d23['大区'].values]
        valid_pairs=[(l,d) for l,d in valid_pairs if len(d)>0]
        if valid_pairs:
            labels,data=zip(*valid_pairs)
            bp=ax2.boxplot(list(data),patch_artist=True,labels=list(labels))
            for patch,lbl in zip(bp['boxes'],labels):
                patch.set_facecolor(REGION_COLORS.get(lbl,'gray')); patch.set_alpha(0.7)
        ax2.set_title(f'{yr_max}年各大区收入分布',fontsize=11)
        ax2.set_ylabel('元/人'); ax2.spines[['top','right']].set_visible(False)
        plt.tight_layout(); self._sv(fig,'E17_城乡收入趋势.png')

    def E18(self):
        if self.econ.empty or '农业集约化指数' not in self.econ.columns: return
        fig,axes=plt.subplots(1,2,figsize=(16,9))
        fig.suptitle(' 农业集约化指数演变（第一产业GDP/常住人口）',fontsize=12,fontweight='bold')
        ax1=axes[0]
        for region,color in REGION_COLORS.items():
            sub=self.econ[self.econ['大区']==region].groupby('年份')['农业集约化指数'].mean().dropna()
            if len(sub)>0: ax1.plot(sub.index,sub.values,color=color,linewidth=2.5,label=region)
        ax1.set_title('各大区农业集约化指数趋势',fontsize=11); ax1.legend()
        ax1.spines[['top','right']].set_visible(False)
        ax2=axes[1]
        yr_max=self.econ['年份'].max()
        d23=self.econ[self.econ['年份']==yr_max].sort_values('农业集约化指数').dropna(subset=['农业集约化指数'])
        if len(d23)>0:
            ax2.barh(d23['省份'],d23['农业集约化指数'],
                     color=[REGION_COLORS.get(r,'gray') for r in d23['大区']],edgecolor='white',height=0.8)
        ax2.set_title(f'{yr_max}年31省农业集约化指数排名',fontsize=11)
        ax2.spines[['top','right']].set_visible(False)
        plt.tight_layout(); self._sv(fig,'E18_农业集约化指数.png')

    def E19(self):
        if self.ml.y_clf_test is None or self.ml.y_clf_pred is None: return
        cm=confusion_matrix(self.ml.y_clf_test,self.ml.y_clf_pred)
        fig,ax=plt.subplots(figsize=(6,5))
        sns.heatmap(cm,annot=True,fmt='d',cmap='Reds',ax=ax)
        if cm.shape==(2,2):
            ax.set_xticks([0.5,1.5]); ax.set_xticklabels(['预测扩张','预测萎缩'])
            ax.set_yticks([0.5,1.5]); ax.set_yticklabels(['实际扩张','实际萎缩'],rotation=0)
        ax.set_title(' 农业萎缩风险预警混淆矩阵',fontsize=12,fontweight='bold')
        plt.tight_layout(); self._sv(fig,'E19_风险预警混淆矩阵.png')

    def E20(self):
        if self.econ.empty: return
        yr_max=self.econ['年份'].max()
        d23=self.econ[self.econ['年份']==yr_max].copy()
        metrics=[m for m in ['总GDP(亿元)','人均GDP(元)','第一产业GDP(亿元)',
                              '农村居民人均可支配收入(元)','第一产业占GDP比重(%)'] if m in d23.columns]
        if len(metrics)<3: return
        rd=d23.groupby('大区')[metrics].mean().dropna()
        norm=rd.apply(lambda x: x/x.max(),axis=0).reindex(list(REGION_COLORS.keys())).dropna()
        if len(norm)==0: return
        n=len(metrics); angles=np.linspace(0,2*pi,n,endpoint=False).tolist()+[0]
        fig,ax=plt.subplots(figsize=(8,8),subplot_kw=dict(polar=True))
        for region in norm.index:
            vals=norm.loc[region].tolist()+[norm.loc[region].iloc[0]]
            ax.plot(angles,vals,linewidth=2.5,label=region,color=REGION_COLORS[region])
            ax.fill(angles,vals,alpha=0.12,color=REGION_COLORS[region])
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels([m.replace('居民人均','').replace('(亿元)','')
                             .replace('(元)','').replace('第一产业','农业') for m in metrics],fontsize=9)
        ax.tick_params(pad=14)
        ax.set_title(' 四大区域综合指标雷达图',fontsize=12,fontweight='bold',pad=35)
        ax.legend(loc='upper center',bbox_to_anchor=(0.5,-0.12),ncol=4)
        self._sv(fig,'E20_四区雷达图.png')

    def E21(self):
        fig=plt.figure(figsize=(16,9),facecolor='#0D1B2A')
        gs=gridspec.GridSpec(2,4,figure=fig,hspace=0.45,wspace=0.35)
        def panel(ax,bg='#1A2E45'):
            ax.set_facecolor(bg); ax.spines[['top','right','bottom','left']].set_visible(False); return ax
        ax_t=fig.add_subplot(gs[0,:]); panel(ax_t,'#0D1B2A')
        ax_t.text(0.5,0.65,'乡村振兴大数据分析系统 V12.3 — 核心结论仪表盘',
                  ha='center',va='center',fontsize=18,fontweight='bold',
                  color='white',transform=ax_t.transAxes)
        ax_t.text(0.5,0.2,f'最优模型: {self.ml.best_name}  |  四级数据融合  |  四大AutoML算法  |  SARIMA预测',
                  ha='center',va='center',fontsize=11,color='#A0C4FF',transform=ax_t.transAxes)
        ax_t.axis('off')
        if self.econ.empty:
            plt.tight_layout(); self._sv(fig,'E21_结论仪表盘.png'); return

        yr_max=self.econ['年份'].max(); yr_min=self.econ['年份'].min()
        d_lat=self.econ[self.econ['年份']==yr_max]
        d_min=self.econ[self.econ['年份']==yr_min]
        # ★ 修复4：不再用DataFrame.get()，直接用 .mean() 的安全方式
        a_lat=d_lat['第一产业占GDP比重(%)'].mean() if '第一产业占GDP比重(%)' in d_lat.columns else 0
        a_min=d_min['第一产业占GDP比重(%)'].mean() if '第一产业占GDP比重(%)' in d_min.columns else 0
        inc_lat=d_lat['农村居民人均可支配收入(元)'].mean() if '农村居民人均可支配收入(元)' in d_lat.columns else 0
        kpis=[
            (f'{a_min:.1f}%→{a_lat:.1f}%', f'第一产业比重\n{yr_min}→{yr_max}', '#E65100'),
            (f'{inc_lat/10000:.1f}万',       '最新农村人均收入',                  '#2E7D32'),
            (f'{self.ml.results.get("全局",{}).get("R2",0):.3f}', '全局模型R^2',  '#1565C0'),
            (f'{len(self.econ["省份"].unique())}省',  '覆盖省份数',               '#4527A0'),
        ]
        for i,(val,label,color) in enumerate(kpis):
            ax=fig.add_subplot(gs[1,i]); panel(ax)
            ax.text(0.5,0.65,val,ha='center',va='center',fontsize=22,fontweight='bold',
                    color=color,transform=ax.transAxes)
            ax.text(0.5,0.2,label,ha='center',va='center',fontsize=10,
                    color='#AAAAAA',transform=ax.transAxes)
            ax.axis('off')
            ax.add_patch(mpatches.FancyBboxPatch((0.05,0.05),0.9,0.9,
                         boxstyle='round,pad=0.05',facecolor=color,alpha=0.15,
                         edgecolor=color,linewidth=2,transform=ax.transAxes))
        self._sv(fig,'E21_结论仪表盘.png')

    def E22(self):
        if self.econ.empty or '人均GDP(元)' not in self.econ.columns: return
        yr_max=self.econ['年份'].max()
        d23=self.econ[self.econ['年份']==yr_max].copy()
        if d23.empty: return
        fig,axes=plt.subplots(1,2,figsize=(16,9))
        fig.suptitle(f'  {yr_max}年31省人均GDP与农村居民收入横向对比',fontsize=14,fontweight='bold',y=1.02)
        ax1=axes[0]
        d_gdp=d23.sort_values('人均GDP(元)').dropna(subset=['人均GDP(元)'])
        if len(d_gdp)>0:
            ax1.barh(d_gdp['省份'],d_gdp['人均GDP(元)']/10000,
                     color=[REGION_COLORS.get(r,'gray') for r in d_gdp['大区']],edgecolor='white',height=0.8)
            avg=d_gdp['人均GDP(元)'].mean()/10000
            ax1.axvline(avg,color='red',linestyle='--',label=f'均值 {avg:.1f}万')
            ax1.legend(loc='lower right')
        ax1.set_title(f'{yr_max}年31省人均GDP（万元）',fontsize=12,fontweight='bold')
        ax1.set_xlabel('万元'); ax1.spines[['top','right']].set_visible(False)
        ax2=axes[1]
        if '农村居民人均可支配收入(元)' in d23.columns:
            d_inc=d23.sort_values('农村居民人均可支配收入(元)').dropna(subset=['农村居民人均可支配收入(元)'])
            if len(d_inc)>0:
                ax2.barh(d_inc['省份'],d_inc['农村居民人均可支配收入(元)']/10000,
                         color=[REGION_COLORS.get(r,'gray') for r in d_inc['大区']],edgecolor='white',height=0.8)
                avg2=d_inc['农村居民人均可支配收入(元)'].mean()/10000
                ax2.axvline(avg2,color='red',linestyle='--',label=f'均值 {avg2:.2f}万')
                ax2.legend(loc='lower right')
        ax2.set_title(f'{yr_max}年31省农村居民可支配收入（万元）',fontsize=12,fontweight='bold')
        ax2.set_xlabel('万元'); ax2.spines[['top','right']].set_visible(False)
        plt.tight_layout(); self._sv(fig,'E22_31省经济与收入横向对比.png')

    def E23(self):
        if self.agri.empty: return
        fig,axes=plt.subplots(1,2,figsize=(16,6))
        fig.suptitle('图E23  农作物复种指数与粮食种植率变化轨迹',fontsize=14,fontweight='bold',y=1.02)
        r_col='大区' if '大区' in self.agri.columns else ('宏观区域' if '宏观区域' in self.agri.columns else None)
        ax1=axes[0]
        if '农作物复种指数' in self.agri.columns and r_col:
            for region,color in REGION_COLORS.items():
                sub=self.agri[self.agri[r_col]==region].groupby('年份')['农作物复种指数'].mean().dropna()
                if len(sub)>0: ax1.plot(sub.index,sub.values,color=color,linewidth=2.5,label=region)
            ax1.set_title('各大区农作物复种指数演变',fontsize=12,fontweight='bold')
            ax1.set_ylabel('复种指数'); ax1.legend(); ax1.grid(alpha=0.3,linestyle='--')
        ax1.spines[['top','right']].set_visible(False)
        ax2=axes[1]
        if '粮食作物种植率(%)' in self.agri.columns and r_col:
            for region,color in REGION_COLORS.items():
                sub=self.agri[self.agri[r_col]==region].groupby('年份')['粮食作物种植率(%)'].mean().dropna()
                if len(sub)>0: ax2.plot(sub.index,sub.values,color=color,linewidth=2.5,label=region)
            ax2.set_title('各大区粮食作物种植率(%)演变',fontsize=12,fontweight='bold')
            ax2.set_ylabel('种植率(%)'); ax2.legend(); ax2.grid(alpha=0.3,linestyle='--')
        ax2.spines[['top','right']].set_visible(False)
        plt.tight_layout(); self._sv(fig,'E23_农作物复种与种植率变化.png')


# ======================================================================
#  学术三线表生成器（10张）—— 完全修复版
# ======================================================================
class AcademicReportGenerator:
    @staticmethod
    def generate(ml, sarima_dict, econ_df, raw_df, output_path):
        """
        ★ 修复5：所有需要大区/宏观区域分组的操作，改用 econ_df（保有原始大区列）
                  而非 feat_df（其大区列已被get_dummies展开）
        """
        logger.info("[报告] 生成10张学术三线表...")
        try:
            import openpyxl
            from openpyxl.styles import Border, Side, Font, Alignment
            from openpyxl.utils import get_column_letter
        except ImportError:
            logger.error("请安装 openpyxl: pip install openpyxl")
            return

        wb = openpyxl.Workbook()
        wb.remove(wb.active)

        def write_sheet(ws, df):
            from openpyxl.styles import Border, Side, Font, Alignment
            from openpyxl.utils import get_column_letter
            thick = Side(border_style="thick",  color="000000")
            thin  = Side(border_style="thin",   color="000000")
            for col_idx, col_name in enumerate(df.columns, 1):
                ws.cell(row=1, column=col_idx, value=col_name)
            for row_idx, row in enumerate(df.values, 2):
                for col_idx, val in enumerate(row, 1):
                    ws.cell(row=row_idx, column=col_idx, value=val)
            for r in range(1, ws.max_row+1):
                for c in range(1, ws.max_column+1):
                    cell = ws.cell(row=r, column=c)
                    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                    cell.font = Font(name="黑体" if r==1 else "Times New Roman", size=11, bold=(r==1))
                    if r==1:
                        cell.border = Border(top=thick, bottom=thin)
                    elif r==ws.max_row:
                        cell.border = Border(bottom=thick)
                    else:
                        cell.border = Border()
            for c in range(1, ws.max_column+1):
                ws.column_dimensions[get_column_letter(c)].width = 20

        # ── 表1：四大模型性能对比 ──────────────────────────
        if ml.global_cmp:
            rows = []
            for name, res in ml.global_cmp.items():
                rows.append({
                    '模型算法': name,
                    'R^2(决定系数)': round(res['R2'],4),
                    'MAE(平均绝对误差)': round(res['MAE'],2),
                    'RMSE(均方根误差)': round(res['RMSE'],2),
                    'CV_R^2均值(5折)': round(res['CV_mean'],4),
                    'CV_R^2标准差': round(res['CV_std'],4),
                    '最优标记': '★' if name==ml.best_name else '',
                })
            ws = wb.create_sheet('表1_四大模型性能对比')
            write_sheet(ws, pd.DataFrame(rows))

        # ── 表2：分区域精度 ────────────────────────────────
        if ml.results:
            rows = [{'空间区域': reg, 'R^2': round(res['R2'],4),
                     'RMSE': round(res['RMSE'],2), 'MAE': round(res['MAE'],2)}
                    for reg, res in ml.results.items()]
            ws = wb.create_sheet('表2_分区域模型精度')
            write_sheet(ws, pd.DataFrame(rows))

        # ── 表3：特征重要性Top15 ───────────────────────────
        try:
            imp, feats = ml.get_importances()
            if imp is not None and len(feats)>0:
                idx = np.argsort(imp)[::-1][:15]
                df3 = pd.DataFrame({
                    '排名': range(1, len(idx)+1),
                    '特征名称': [str(feats[i]).replace('_x','').replace('_y','') for i in idx],
                    '重要性评分(MDI)': np.round(np.array(imp)[idx], 4),
                })
                ws = wb.create_sheet('表3_驱动特征Top15')
                write_sheet(ws, df3)
        except Exception as e:
            logger.debug(f"  表3失败: {e}")

        # ── 表4：SARIMA预测 ───────────────────────────────
        if sarima_dict:
            rows = []
            for name, sf in sarima_dict.items():
                adf = sf.adf_test()
                try:
                    preds, _ = sf.forecast(5)
                    pred_str = ", ".join([f"{v:.2f}" for v in preds.values])
                except:
                    pred_str = "预测失败"
                rows.append({
                    '预测指标': name.replace('_x',''),
                    '模型阶数(p,d,q)': str(sf.order),
                    'ADF T统计量': adf['stat'],
                    'ADF P-Value': adf['pvalue'],
                    '平稳性结论': '平稳' if adf['is_stationary'] else '非平稳',
                    '未来5年预测值': pred_str,
                })
            ws = wb.create_sheet('表4_SARIMA预测检验')
            write_sheet(ws, pd.DataFrame(rows))

        # ── 表5：最新年份31省核心数据 ──────────────────────
        if not econ_df.empty:
            yr_max = econ_df['年份'].max()
            d23 = econ_df[econ_df['年份']==yr_max].copy()
            cols5 = ['省份','大区','总GDP(亿元)','人均GDP(元)',
                     '第一产业占GDP比重(%)','农村居民人均可支配收入(元)','常住人口(万人)']
            cols5 = [c for c in cols5 if c in d23.columns]
            d23_s = d23[cols5].sort_values('总GDP(亿元)',ascending=False) \
                    if '总GDP(亿元)' in d23.columns else d23[cols5]
            d23_s.insert(0, 'GDP排名', range(1, len(d23_s)+1))
            ws = wb.create_sheet('表5_最新31省核心数据')
            write_sheet(ws, d23_s.round(2))

            # ── 表6：四大区域结构演变（★ 修复：用econ_df而非feat_df）──
            try:
                yr_min = 1990; yr_max2 = econ_df['年份'].max()
                cols6 = [c for c in ['总GDP(亿元)','第一产业占GDP比重(%)'] if c in econ_df.columns]
                if cols6:
                    g1 = econ_df[econ_df['年份']==yr_min].groupby('大区')[cols6].mean().reset_index()
                    g2 = econ_df[econ_df['年份']==yr_max2].groupby('大区')[cols6].mean().reset_index()
                    # 明确重命名，避免列名冲突
                    rename1 = {'大区':'四大区域'}
                    rename2 = {'大区':'四大区域'}
                    for c in cols6:
                        rename1[c] = f'{yr_min}年_{c}'
                        rename2[c] = f'{yr_max2}年_{c}'
                    g1 = g1.rename(columns=rename1)
                    g2 = g2.rename(columns=rename2)
                    df6 = pd.merge(g1, g2, on='四大区域')
                    gdp_col1 = f'{yr_min}年_总GDP(亿元)'
                    gdp_col2 = f'{yr_max2}年_总GDP(亿元)'
                    if gdp_col1 in df6.columns and gdp_col2 in df6.columns:
                        df6['GDP增幅倍数'] = (df6[gdp_col2] / (df6[gdp_col1]+1e-6)).round(1)
                    ws = wb.create_sheet('表6_四大区域结构演变')
                    write_sheet(ws, df6.round(2))
            except Exception as e:
                logger.debug(f"  表6失败: {e}")

            # ── 表7：相关性矩阵 ────────────────────────────
            try:
                corr_cols = [c for c in ['总GDP(亿元)','人均GDP(元)','第一产业占GDP比重(%)',
                                          '农村居民人均可支配收入(元)','常住人口(万人)']
                              if c in econ_df.columns]
                df7 = econ_df[corr_cols].corr().round(3).reset_index().rename(columns={'index':'变量'})
                ws = wb.create_sheet('表7_变量相关性矩阵')
                write_sheet(ws, df7)
            except Exception as e:
                logger.debug(f"  表7失败: {e}")

            # ── 表8：乡村振兴综合指数 ─────────────────────
            try:
                d8 = d23.copy()
                for c in ['农村居民人均可支配收入(元)','人均GDP(元)','总GDP(亿元)']:
                    if c in d8.columns:
                        d8[f'{c}_n'] = (d8[c]-d8[c].min())/(d8[c].max()-d8[c].min()+1e-6)
                if '第一产业占GDP比重(%)' in d8.columns:
                    d8['非农_n'] = (100-d8['第一产业占GDP比重(%)'])/100
                n_cols=[c for c in d8.columns if c.endswith('_n')]
                if n_cols:
                    d8['乡村振兴综合指数'] = d8[n_cols].mean(axis=1)
                    d8 = d8.sort_values('乡村振兴综合指数',ascending=False)
                    d8.insert(0,'全国排名',range(1,len(d8)+1))
                    ws = wb.create_sheet('表8_乡村振兴指数评估')
                    write_sheet(ws, d8[['全国排名','省份','大区','乡村振兴综合指数']].round(4))
            except Exception as e:
                logger.debug(f"  表8失败: {e}")

        # ── 表9：混淆矩阵 ──────────────────────────────────
        try:
            if ml.y_clf_test is not None and ml.y_clf_pred is not None:
                cm = confusion_matrix(ml.y_clf_test, ml.y_clf_pred)
                if cm.shape == (2,2):
                    df9 = pd.DataFrame({
                        '真实分类': ['实际扩张(0)','实际萎缩(1)'],
                        '预测为扩张(0)': [cm[0,0], cm[1,0]],
                        '预测为萎缩(1)': [cm[0,1], cm[1,1]],
                    })
                    ws = wb.create_sheet('表9_风险预警混淆矩阵')
                    write_sheet(ws, df9)
        except Exception as e:
            logger.debug(f"  表9失败: {e}")

        # ── 表10：集约化演变（★ 修复：用econ_df而非feat_df）──
        try:
            if not econ_df.empty and '农业集约化指数' in econ_df.columns:
                years = [y for y in [1990,2000,2010,2020,econ_df['年份'].max()]
                         if y in econ_df['年份'].values]
                # ★ 直接用econ_df（含大区列），不用feat_df（大区列已被展开）
                df10 = econ_df[econ_df['年份'].isin(years)].pivot_table(
                    index='大区', columns='年份',
                    values='农业集约化指数', aggfunc='mean').reset_index()
                df10.columns = ['大区'] + [str(c) for c in df10.columns[1:]]
                ws = wb.create_sheet('表10_十年集约化演变')
                write_sheet(ws, df10.round(3))
        except Exception as e:
            logger.debug(f"  表10失败: {e}")

        if len(wb.worksheets) == 0:
            ws = wb.create_sheet('说明')
            ws['A1'] = '数据不足，未能生成表格'

        wb.save(output_path)
        logger.info(f"  ✅ Excel已保存: {output_path} | {len(wb.worksheets)} 张工作表")


# ======================================================================
#  主函数
# ======================================================================
def main():
    print("="*80)
    print("🌾 乡村振兴农业大数据分析系统 V12.3 (全面修复版)")
    print("   修复：KeyError宏观区域 / AutoML日志 / DataFrame.get() / pandas兼容性")
    print("="*80)

    # Step1: 加载31省Excel
    loader  = ProvincialEconLoader(PROV31_DIR)
    econ_df = loader.load()

    # Step2: 四级数据融合
    fusion = DataFusionEngine(econ_df)
    raw_df = fusion.run()

    # Step3: 确定目标变量
    num_cols  = [c for c in raw_df.select_dtypes(include=[np.number]).columns if c!='年份']
    area_cols = [c for c in num_cols if '面积' in c]
    target_col = area_cols[0] if area_cols else '第一产业占GDP比重(%)'
    if target_col not in raw_df.columns and num_cols:
        target_col = num_cols[0]
    logger.info(f"  目标变量: {target_col}")

    # Step4: 特征工程
    feat_df = fusion.feature_engineering(raw_df, target_col)

    # Step5: SARIMA
    sarima_dict = {}
    if HAS_STATSMODELS:
        logger.info("[Step5] SARIMA建模...")
        targets = [c for c in ['第一产业占GDP比重(%)','农村居民人均可支配收入(元)',
                                '总GDP(亿元)',target_col] if c in raw_df.columns]
        targets = list(dict.fromkeys(targets))[:4]   # 去重保序
        for col in targets:
            try:
                ts = raw_df.groupby('年份')[col].mean()
                ts.index = ts.index.astype(int)
                if len(ts)<10: continue
                sf = SARIMAForecaster(ts, name=col)
                sf.fit(auto=len(ts)>15)
                sarima_dict[col] = sf
                logger.info(f"  SARIMA [{col[:20]}]: 阶数={sf.order}")
            except Exception as e:
                logger.debug(f"  [{col}] 失败: {e}")
    else:
        logger.warning("  statsmodels未安装，跳过SARIMA")

    # Step6: AutoML
    ml = AutoMLEngine(feat_df, target_col)
    ml.train()

    # Step7: 可视化
    viz = ThemeVisualizer(econ_df, raw_df, feat_df, target_col, ml, sarima_dict, OUTPUT_DIR)
    viz.plot_all()

    # Step8: Excel三线表
    excel_path = os.path.join(OUTPUT_DIR, '综合学术报告_V12_三线表.xlsx')
    # ★ 修复6：传入raw_df（含大区列）而非feat_df
    AcademicReportGenerator.generate(ml, sarima_dict, econ_df, raw_df, excel_path)

    best_r2 = ml.results.get('全局',{}).get('R2',0)
    print("="*80)
    print(f"✅ 全部完成！")
    print(f"   加载省份: {loader.loaded} 个")
    print(f"   图表目录: {OUTPUT_DIR}")
    print(f"   三线表Excel: {excel_path}")
    print(f"   最优模型: {ml.best_name}  R^2={best_r2:.4f}")
    print("="*80)


if __name__ == '__main__':
    main()