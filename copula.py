
import sys

import scipy
import numpy as np
from scipy.integrate import quad
from scipy.optimize import fmin

import utils



class CopulaException(Exception):
    pass

class Copula(object):
    def __init__(self,U,V,theta=None,cname=None,dev=False):
        """Instantiates an instance of the copula object from a pandas dataframe
        
        :param data: the data matrix X
        :param utype: the distribution for the univariate, can be 'kde','norm'
        :param cname: the choice of copulas, can be 'clayton','gumbel','frank','gaussian'  

        """
        self.U = U
        self.V = V
        self.theta = theta
        self.cname = cname
        self.tau = scipy.stats.kendalltau(self.U, self.V)[0]
        if cname:
            self._get_parameter()
            self.cdf = self._get_cdf()
        if dev:
            self.derivative=self._get_du()



    def density_gaussian(self,u):
        """Compute density of gaussian copula
        """
        R = cholesky(self.param)
        x = norm.ppf(u)
        z = solve(R,x.T)
        log_sqrt_det_rho = np.sum(np.log(np.diag(R)))
        y = np.exp(-0.5 * np.sum( np.power(z.T,2) - np.power(x,2) , axis=1 ) - log_sqrt_det_rho)
        return y

    def _get_parameter(self):
        """ estimate the parameter (theta) of copula given tau
        """        
        
        if self.cname == 'clayton':
            if self.tau == 1:
                self.theta = 10000
            else:
                self.theta = 2*self.tau/(1-self.tau)
            
        elif self.cname == 'frank':
            self.theta = -fmin(self._frank_help, -5, disp=False)[0]
            
        elif self.cname == 'gumbel':
            if self.tau == 1:
                self.theta = 10000
            else:
                self.theta = 1/(1-self.tau)



    def _frank_help(self,alpha):
        """compute first order debye function to estimate theta
        """

        debye = lambda t: t/(np.exp(t)-1)
        debye_value = quad(debye, sys.float_info.epsilon, alpha)[0]/alpha
        diff = (1-self.tau)/4.0  - (debye(-alpha)-1)/alpha
        return np.power(diff,2)


    def _get_cdf(self):
        """Compute copula cdf
        """
        if self.cname == 'clayton':
            def cdf(U,V,theta):
                if theta < 0:
                    raise ValueError("Theta cannot be than 0 for clayton")
                elif theta == 0:
                    return np.multiply(U,V)
                else:
                    cdf=[np.power(np.power(U[i],-theta)+np.power(V[i],-theta)-1,-1.0/theta) if U[i]>0 else 0 for i in range(len(U))]
                    return [max(x,0) for x in cdf]
            return cdf

        elif self.cname =='frank':
            def cdf(U,V,theta):
                if theta < 0:
                    raise ValueError("Theta cannot be less than 0 for Frank")
                elif theta == 0:
                    return np.multiply(U,V)
                else:
                    num = np.multiply(np.exp(np.multiply(-theta,U))-1,np.exp(np.multiply(-theta,V))-1)
                    den = np.exp(-theta)-1
                    return -1.0/theta*np.log(1+num/den)
            return cdf

        elif self.cname == 'gumbel':
            def cdf(U,V,theta):
                if theta < 1:
                    raise ValueError("Theta cannot be less than 1 for Gumbel")
                elif theta == 1:
                    return np.multiply(U,V)
                else:
                    cdfs=[]
                    for i in range(len(U)):
                        if U[i] == 0:
                            cdfs.append(0)
                        else:
                            h = np.power(-np.log(U[i]),theta)+np.power(-np.log(V[i]),theta)
                            h = -np.power(h,1.0/theta)
                            cdfs.append(np.exp(h))
                    return cdfs
            return cdf

        else:
            raise Exception('Unsupported distribution: ' + str(self.cname))
            


    def _get_du(self):
        """Compute partial derivative of each copula function
        :param theta: single parameter of the Archimedean copula
        :param cname: name of the copula function
        """
        if self.cname == 'clayton':
            def du(u,v,theta):
                if theta == 0:
                    return v
                else:
                    A = pow(u,theta)
                    B = pow(u,-theta)-1
                    h = 1+np.multiply(A,B)
                    h = pow(h,(-1-theta)/theta)
                    return h
            return du

        elif self.cname =='frank':
            def du(u,v,theta):
                if theta == 0:
                    return v
                else:
                    g = lambda theta,z:-1+np.exp(-np.dot(theta,z))
                    num = np.multiply(g(u,theta),g(v,theta))+g(v,theta)
                    den = np.multiply(g(u,theta),g(v,theta))+g(1,theta)
                    return num/den
            return du

        elif self.cname == 'gumbel':
            def du(u,v,theta):
                if theta == 1:
                    return v
                else:
                    p1 = Copula(u,v,theta,'gumbel').cdf(u,v,theta)
                    p2 = np.power(np.power(-np.log(u),theta)+np.power(-np.log(v),theta),-1+1.0/theta)
                    p3 = np.power(-np.log(u),theta-1)
                    return np.divide(np.multiply(np.multiply(p1,p2),p3),u)
            return du
        else:
            raise Exception('Unsupported distribution: ' + str(self.cname))
            

    
    @staticmethod
    def compute_empirical(u,v):
        """compute empirical distribution 
        """
        z_left,z_right=[],[]
        L,R=[],[]
        N = len(u)
        base = np.linspace(0.0,1.0,50)
        for k in range(len(base)):
            left = sum(np.logical_and(u <= base[k],v<= base[k]))/N
            right = sum(np.logical_and(u >= base[k],v>= base[k]))/N
            if left>0:
                z_left.append(base[k])
                L.append(left/base[k]**2)
            if right>0:
                z_right.append(base[k])
                R.append(right/(1-z_right[k])**2)
        return z_left,L,z_right,R


    @staticmethod
    def select_copula(U,V):
        """Select best copula function based on likelihood
        """
        clayton_c = Copula(U,V,cname ='clayton')
        frank_c = Copula(U,V,cname ='frank')
        gumbel_c = Copula(U,V,cname ='gumbel')
        theta_c = [clayton_c.theta,frank_c.theta,gumbel_c.theta]
        if clayton_c.tau <= 0:
            bestC = 2
            paramC = frank_c.theta
            return bestC,paramC
        z_left,L,z_right,R = Copula.compute_empirical(U,V)
        left_dependence,right_dependence=[],[]
        left_dependence.append(clayton_c.cdf(z_left,z_left,clayton_c.theta)/np.power(z_left,2))
        left_dependence.append(frank_c.cdf(z_left,z_left,frank_c.theta)/np.power(z_left,2))
        left_dependence.append(gumbel_c.cdf(z_left,z_left,gumbel_c.theta)/np.power(z_left,2))
        g = lambda c,z: np.divide(1.0-2*np.asarray(z)+c,np.power(1.0-np.asarray(z),2))
        right_dependence.append(g(clayton_c.cdf(z_right,z_right,clayton_c.theta),z_right))
        right_dependence.append(g(frank_c.cdf(z_right,z_right,frank_c.theta),z_right))
        right_dependence.append(g(gumbel_c.cdf(z_right,z_right,gumbel_c.theta),z_right))
        #compute L2 distance from empirical distribution
        cost_L =  [np.sum((L-l)**2) for l in left_dependence]
        cost_R =  [np.sum((R-r)**2) for r in right_dependence]
        cost_LR =  cost_L+cost_R
        bestC = np.argmax(cost_LR)
        paramC = theta_c[bestC]
        return bestC,paramC

       


if __name__ == '__main__':
    #quick test
    c0 = Copula([0.1,0.2,0.3,0.4],[0.5,0.6,0.5,0.8],cname='clayton')
    # print(c0.cdf([0,0.1,0.2],[0,0.1,0.8],c0.theta))
    
    c1 = Copula([0.1,0.2,0.3,0.4],[0.5,0.6,0.5,0.8],cname='frank')
    # print(c1.cdf([0,0.1,0.2],[0,0.1,0.2],c1.theta))

    c2 = Copula([0.1,0.2,0.3,0.4],[0.5,0.6,0.5,0.8],cname='gumbel')
    # print(c2.cdf([0,0.1,0.2],[0,0.1,0.8],c2.theta))

    U=[0.1,0.2,0.3,0.4]
    V=[0.2,0.15,0.3,0.5]
    # print(Copula.select_copula(U,V))



                










